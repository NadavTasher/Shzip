import os
import sys
import typing
import pytest
import hashlib
import tempfile
import subprocess


def extract(file=None, contents=None, environment={}) -> str:
    # Create an extraction path
    temp_path = tempfile.mktemp()

    # Create environment variables
    env = {"TARGET": temp_path}
    env.update(environment)

    # Make sure variables are defined
    assert file or contents, "Must pass file or contents"

    if file:
        # Make the file executable
        os.chmod(file, 0o777)

        # Execute the archive
        subprocess.run([file], env=env, capture_output=False, check=True)
    else:
        # Pipe the archive to a shell
        subprocess.run(["/bin/sh"], input=contents, env=env, capture_output=False, check=True)

    # Return the extraction path
    return temp_path


def shzip(*args, input: typing.Optional[bytes] = None) -> bytes:
    # Execute shzip with the arguments
    process = subprocess.run([sys.executable, "src/shzip/shzip.py"] + list(args), input=input, capture_output=True, check=False)

    # Raise an exception if failed
    if process.returncode != 0:
        raise Exception(process.stderr)
    
    print(process.stdout)

    # Return the stdout
    return process.stdout


def test_empty_archive():
    # Create empty archive in file
    with pytest.raises(Exception):
        shzip()


def test_archive_to_stdout():
    # Create temporary file
    temp_path = tempfile.mktemp()

    # Write some data to the file
    with open(temp_path, "w") as file:
        file.write("HelloWorld")

    # Archive the file
    assert b"HelloWorld" in shzip(temp_path)


def test_archive_to_file():
    # Create output path
    output_path = tempfile.mktemp()

    # Create temporary file
    temp_path = tempfile.mktemp()

    # Write some data to the file
    with open(temp_path, "w") as file:
        file.write("HelloWorld")

    # Archive the file
    assert b"HelloWorld" not in shzip("-f", output_path, temp_path)

    # Make sure the file exists
    assert os.path.isfile(output_path)

    # Make sure the file is an archive
    with open(output_path, "rb") as file:
        assert b"HelloWorld" in file.read()

    # Execute the archive to extract
    extraction_path = extract(file=output_path)

    # Make sure the file exists
    assert os.path.isfile(os.path.join(extraction_path, temp_path.lstrip("./")))


def test_archive_multiple_files():
    # List of temporary files
    temp_paths = []

    # Create temporary files
    for index in range(10):
        # Create current path
        temp_path = tempfile.mktemp()

        # Write to the file
        with open(temp_path, "w") as file:
            file.write(os.urandom(11 * index).hex())

        # Append the path to the list
        temp_paths.append(temp_path)

    # Extract one of the archives
    extraction_path = extract(contents=shzip(*temp_paths))

    # Make sure the files exists
    for temp_path in temp_paths:
        assert os.path.isfile(os.path.join(extraction_path, temp_path.lstrip("./")))


def test_archive_reproducable():
    # Create temporary file
    temp_path = tempfile.mktemp()

    # Write some data to the file
    with open(temp_path, "wb") as file:
        file.write(os.urandom(1024))

    # Archive the files
    archive_1 = shzip("--reproducable", temp_path)
    archive_2 = shzip("--reproducable", temp_path)

    # Archives should be the same size
    assert archive_1 == archive_2

    # Extract one of the archives
    extraction_path = extract(contents=archive_1)

    # Calculate md5sum before archive
    with open(temp_path, "rb") as file:
        original_md5sum = hashlib.md5(file.read()).digest()

    # Calculate after md5sum
    with open(os.path.join(extraction_path, temp_path.lstrip("./")), "rb") as file:
        extracted_md5sum = hashlib.md5(file.read()).digest()

    # Make sure md5sums match
    assert extracted_md5sum == original_md5sum


def test_archive_non_reproducable():
    # Create temporary file
    temp_path = tempfile.mktemp()

    # Write some data to the file
    with open(temp_path, "wb") as file:
        file.write(os.urandom(1024))

    # Archive the files
    archive_1 = shzip(temp_path)
    archive_2 = shzip(temp_path)

    # Archives should be the same size
    assert len(archive_1) == len(archive_2)

    # Extract one of the archives
    extraction_path = extract(contents=archive_1)

    # Calculate md5sum before archive
    with open(temp_path, "rb") as file:
        original_md5sum = hashlib.md5(file.read()).digest()

    # Calculate after md5sum
    with open(os.path.join(extraction_path, temp_path.lstrip("./")), "rb") as file:
        extracted_md5sum = hashlib.md5(file.read()).digest()

    # Make sure md5sums match
    assert extracted_md5sum == original_md5sum


def test_archive_integrity_plain():
    # Create temporary file
    temp_path = tempfile.mktemp()

    # Write some data to the file
    with open(temp_path, "wb") as file:
        file.write(bytearray([x for x in range(256)] * 10))

    # Calculate md5sum before archive
    with open(temp_path, "rb") as file:
        original_md5sum = hashlib.md5(file.read()).digest()

    # Create and extract the archive
    extraction_path = extract(contents=shzip(temp_path))

    # Calculate after md5sum
    with open(os.path.join(extraction_path, temp_path.lstrip("./")), "rb") as file:
        extracted_md5sum = hashlib.md5(file.read()).digest()

    # Make sure md5sums match
    assert extracted_md5sum == original_md5sum


def test_archive_integrity_gzip():
    # Create temporary file
    temp_path = tempfile.mktemp()

    # Write some data to the file
    with open(temp_path, "wb") as file:
        file.write(bytearray([x for x in range(256)] * 10))

    # Calculate md5sum before archive
    with open(temp_path, "rb") as file:
        original_md5sum = hashlib.md5(file.read()).digest()

    # Create and extract the archive
    extraction_path = extract(contents=shzip("-z", temp_path))

    # Calculate after md5sum
    with open(os.path.join(extraction_path, temp_path.lstrip("./")), "rb") as file:
        extracted_md5sum = hashlib.md5(file.read()).digest()

    # Make sure md5sums match
    assert extracted_md5sum == original_md5sum


def test_archive_integrity_bzip2():
    # Create temporary file
    temp_path = tempfile.mktemp()

    # Write some data to the file
    with open(temp_path, "wb") as file:
        file.write(bytearray([x for x in range(256)] * 10))

    # Calculate md5sum before archive
    with open(temp_path, "rb") as file:
        original_md5sum = hashlib.md5(file.read()).digest()

    # Create and extract the archive
    extraction_path = extract(contents=shzip("-j", temp_path))

    # Calculate after md5sum
    with open(os.path.join(extraction_path, temp_path.lstrip("./")), "rb") as file:
        extracted_md5sum = hashlib.md5(file.read()).digest()

    # Make sure md5sums match
    assert extracted_md5sum == original_md5sum


def test_archive_integrity_xz():
    # Create temporary file
    temp_path = tempfile.mktemp()

    # Write some data to the file
    with open(temp_path, "wb") as file:
        file.write(bytearray([x for x in range(256)] * 10))

    # Calculate md5sum before archive
    with open(temp_path, "rb") as file:
        original_md5sum = hashlib.md5(file.read()).digest()

    # Create and extract the archive
    extraction_path = extract(contents=shzip("-J", temp_path))

    # Calculate after md5sum
    with open(os.path.join(extraction_path, temp_path.lstrip("./")), "rb") as file:
        extracted_md5sum = hashlib.md5(file.read()).digest()

    # Make sure md5sums match
    assert extracted_md5sum == original_md5sum


def test_archive_integrity_incremental():
    # List of temporary files
    temp_paths = {}

    # Create temporary files
    for index in range(256):
        # Create current path
        temp_path = tempfile.mktemp()

        # Create temporary data
        temp_data = bytes([x for x in range(index)])

        # Write to the file
        with open(temp_path, "wb") as file:
            file.write(temp_data)

        # Append the path to the list
        temp_paths[temp_path] = hashlib.md5(temp_data).digest()

    # Create and extract the archive
    extraction_path = extract(contents=shzip(*temp_paths.keys()))

    # Calculate after md5sum
    for temp_path, expected_md5sum in temp_paths.items():
        with open(os.path.join(extraction_path, temp_path.lstrip("./")), "rb") as file:
            extracted_md5sum = hashlib.md5(file.read()).digest()

        # Make sure md5sums match
        assert extracted_md5sum == expected_md5sum
