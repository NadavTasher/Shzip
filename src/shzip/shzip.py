import os
import shlex
import argparse

def main():
	# Create argument parser
	parser = argparse.ArgumentParser()

	# Output arguments
	parser.add_argument('-f', '--file', type=str, action='store', help='Output file', default='/dev/stdout')
	parser.add_argument('--shell', type=str, action='store', help='Shell to use', default='/bin/sh')
	parser.add_argument('--target', type=str, action='store', help='Target directory for extraction', default='.')

	# Create compression group
	compression = parser.add_mutually_exclusive_group()
	compression.add_argument('-z', '--gzip', action='store_true', help='Compress files using gzip')
	compression.add_argument('-j', '--bzip2', action='store_true', help='Compress files using gzip')
	compression.add_argument('-J', '--xz', action='store_true', help='Compress files using gzip')

	# Add input arguments
	parser.add_argument("-T", "--files-from", type=str, action='store', help='Path to a list of files to archive')
	parser.add_argument("paths", type=str, action='store', nargs="*", help="Paths to archive")

	# Parse the arguments
	arguments = parser.parse_args()

	# Create list of paths to use


	# Placeholder lists
	links_to_create = []
	files_to_archive = []
	directories_to_create = []

	# Determine which paths have to be archived
	for path in arguments.paths:
		# For files, add file to archive and parent directory to directories
		if os.path.isfile(path):
			# Append file to archive
			files_to_archive.append(path)

			# Append parent directory
			directories_to_create.append(os.path.dirname(path))

	# Open the output file for writing
	with open(arguments.file, 'wb') as output_file:
		# Write the shebang
		output_file.write(f'#!{arguments.shell}\n'.encode())

		# Determine target path from environment
		output_file.write(f'test -z "$TARGET" && _TARGET={shlex.quote(arguments.target)} || _TARGET="$TARGET"\n'.encode())

		# Create all directories
		for directory_to_create in sorted(directories_to_create, key=len):
			output_file.write(f'mkdir -p $_TARGET/{shlex.quote(directory_to_create.lstrip("/"))}\n'.encode())

		# Archive all files
		for file_to_archive in files_to_archive:
			# Generate termination magic
			termination_magic = os.urandom(10).hex()

			# Write the dumping function
			output_file.write(f'head -c -1 > $_TARGET/{shlex.quote(file_to_archive.lstrip("/"))} << {termination_magic}\n'.encode())

			# Open the file for reading
			with open(file_to_archive, "rb") as file:
				# Fetch file contents
				contents = file.read()

			# Escape special characters
			for character in [b"\\", b"$"]:
				contents = contents.replace(character, b"\\" + character)

			# Write the contents
			output_file.write(contents)

			# Write the termination string
			output_file.write(f'\n{termination_magic}\n'.encode())



if __name__ == '__main__':
	main()