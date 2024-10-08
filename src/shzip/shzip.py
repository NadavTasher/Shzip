import os
import sys
import stat
import shlex
import typing
import base64
import argparse
import subprocess


def process_path(path: str, dereference: bool, files: typing.Set[str], directories: typing.Set[str], symlinks: typing.Set[str]) -> None:
    # Make sure the path does not already exist
    if path in files or path in directories or path in symlinks:
        return

    # Stat the path to check type
    stat_result = os.stat(path, follow_symlinks=dereference)

    # If the path is a symlink, add a symlink
    if stat.S_ISLNK(stat_result.st_mode):
        # Add the path to the symlinks set
        symlinks.add((path, os.readlink(path)))

        # Add the parent directory path to the directories set
        directories.add(os.path.dirname(path))
    elif stat.S_ISREG(stat_result.st_mode):
        # Add the path to the files set
        files.add(path)

        # Add the parent directory path to the directories set
        directories.add(os.path.dirname(path))
    elif stat.S_ISDIR(stat_result.st_mode):
        # List the files in the directory and handle them all
        for child in os.listdir(path):
            process_path(os.path.join(path, child), dereference, files, directories, symlinks)


def process_file(path: str, arguments: argparse.Namespace, output_file: typing.BinaryIO) -> None:
    # Open the file for reading
    with open(path, "rb") as file:
        # Fetch file contents
        contents = file.read()

    if not contents:
        # If contents are empty, just create the file
        output_file.write(f'echo > $TARGET/{shlex.quote(path.lstrip("./"))}'.encode())

        # Nothing more to do
        return

    # Initialize filter
    decoding_command = None
    decompression_command = None

    # Decide on a compression filter
    if arguments.gzip:
        # Set the decompression command
        decompression_command = "( gzip -d || gunzip )"

        # Compress the contents using gzip
        contents = subprocess.run(["gzip", "-9"], input=contents, capture_output=True, check=True).stdout
    elif arguments.bzip2:
        # Set the decompression command
        decompression_command = "( bzip2 -d || bzcat )"

        # Compress the contents using bzip2
        contents = subprocess.run(["bzip2"], input=contents, capture_output=True, check=True).stdout
    elif arguments.xz:
        # Set the decompression command
        decompression_command = "( xz -d || unxz )"

        # Compress the contents using xz
        contents = subprocess.run(["xz", "-e9"], input=contents, capture_output=True, check=True).stdout

    # Will the input be encoded using base64?
    if min(contents) <= 32 or max(contents) >= 128:
        # Set the decoding command
        decoding_command = "base64 -d"

        # Encode the contents
        contents = base64.b64encode(contents)

    # Join all of the commands
    filter_command = " | ".join(filter(bool, [decoding_command, decompression_command]))

    # Generate file separation magic
    eof_magic = os.urandom(10).hex()
    
    # If output should be reproducable, overwrite separation magic
    if arguments.reproducable:
        eof_magic = "SHZIP_EOF"

    # Write the dumping function
    output_file.write(f'( head -c -1 | {filter_command or "cat"} ) > $TARGET/{shlex.quote(path.lstrip("./"))} << {eof_magic}\n'.encode())

    # Write the contents
    output_file.write(contents)

    # Write the termination string
    output_file.write(f'\n{eof_magic}\n'.encode())


def check_prerequisites(prerequisites, arguments, output_file):
    if arguments.skip_prerequisites:
        return
    
    output_file.write(f'( {" || ".join(f"which {shlex.quote(prereqisite)}" for prereqisite in prerequisites)} ) || echo Unable to find prerequisites {shlex.quote(repr(prerequisites))}; exit 127'.encode())

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(add_help=False)

    # Add special arguments
    parser.add_argument('--reproducable', action='store_true', help='Create reproducable archives')
    parser.add_argument('--shell', type=str, action='store', help='Shell to use for the output file', default='/bin/sh')
    parser.add_argument('--target', type=str, action='store', help='Target directory for extraction', default='.')

    # Create compression group
    compression = parser.add_mutually_exclusive_group()
    compression.add_argument('-z', '--gzip', action='store_true', help='Compress files using gzip')
    compression.add_argument('-j', '--bzip2', action='store_true', help='Compress files using bzip2')
    compression.add_argument('-J', '--xz', action='store_true', help='Compress files using xz')

    # Create validation group
    validation = parser.add_mutually_exclusive_group()
    validation.add_argument('--md5', action='store_true', help='Validate files using md5sum')
    validation.add_argument('--sha1', action='store_true', help='Validate files using sha1sum')
    validation.add_argument('--sha256', action='store_true', help='Validate files using sha256sum')
    validation.add_argument('--sha512', action='store_true', help='Validate files using sha512sum')

    # Add POSIX compatible arguments
    parser.add_argument('-f', '--file', type=str, action='store', help='Use archive file or device file')
    parser.add_argument("-T", "--files-from", type=str, action='store', help='Get names to create from file')
    parser.add_argument("-C", "--directory", type=str, action='store', help="Change to directory before performing any operations")
    parser.add_argument("-h", "--dereference", action='store_true', help='Follow symlinks; archive and dump the files they point to.')
    parser.add_argument("paths", type=str, action='store', nargs="*", help="Paths to archive")

    # Parse the arguments
    arguments = parser.parse_args()

    # Create a set of paths to loop over
    paths_to_process = set()

    # Lists of things to create
    files_to_dump, directories_to_create, symlinks_to_link = set(), set(), set()

    # Add paths to process from args
    if arguments.paths:
        paths_to_process |= set(arguments.paths)

    # Add paths to process from file
    if arguments.files_from:
        # Read file list
        with open(arguments.files_from, "r") as files_from_file:
            paths_to_process |= set(files_from_file.read().splitlines())

    # Make sure there are paths to process
    assert paths_to_process, "Refusing to create empty archive"

    # Change directory if required before any further processing
    if arguments.directory:
        os.chdir(arguments.directory)

    # Process all paths
    for path in paths_to_process:
        process_path(path, arguments.dereference, files_to_dump, directories_to_create, symlinks_to_link)

    # Initialize the default output file
    output_file = sys.stdout.buffer

    # Open the output file
    if arguments.file:
        output_file = open(arguments.file, "wb")

    # Write the shebang
    output_file.write(f'#!{arguments.shell}\n'.encode())

    # Make sure the decompressor exists
    if arguments.gzip:
        # Write the decompressor check
        check_prerequisites(["gzip", "gunzip"], arguments, output_file)
    elif arguments.bzip2:
        # Write the decompressor check
        check_prerequisites(["bzip2", "bzcat"], arguments, output_file)
    elif arguments.xz:
        # Write the decompressor check
        check_prerequisites(["xz", "unxz"], arguments, output_file)

    # Determine target path from environment
    output_file.write(f'test -z "$TARGET" && TARGET={shlex.quote(arguments.target)}\n'.encode())

    # Create all directories
    for directory_to_create in sorted(directories_to_create, key=len):
        output_file.write(f'mkdir -p $TARGET/{shlex.quote(directory_to_create.lstrip("./"))}\n'.encode())

    # Archive all files
    for file_to_dump in files_to_dump:
        # Process the file contents
        process_file(file_to_dump, arguments, output_file)

    for symlink, target in symlinks_to_link:
        # Create symlink to target
        output_file.write(f'ln -s {shlex.quote(target)} $TARGET/{shlex.quote(symlink.lstrip("./"))}\n'.encode())


if __name__ == '__main__':
    main()
