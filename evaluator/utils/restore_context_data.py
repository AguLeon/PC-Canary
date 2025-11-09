import os
import subprocess


def restore_context_data(from_path: str, to_path: str) -> bool:
    """
    Incrementally update all contents from the 'from_path' directory to the 'to_path' directory.

    Args:
        from_path: Source directory path
        to_path: Destination directory path

    Returns:
        bool: True if the operation succeeds, otherwise False
    """
    # Check if source path exists
    if not os.path.exists(from_path):
        raise Exception(f"User data {from_path} does not exist")

    # Create destination directory if it doesn't exist
    os.makedirs(to_path, exist_ok=True)

    # Copy contents from source to destination using rsync
    try:
        rsync_cmd = ["rsync", "-av", "--delete", "--chmod=F644", f"{from_path}/", to_path]
        result = subprocess.run(
            rsync_cmd,
            check=True,  # Raise an exception if the command fails
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error occurred during incremental update: {str(e.stderr)}")
    except Exception as e:
        raise Exception(f"Error occurred during incremental update: {str(e)}")
