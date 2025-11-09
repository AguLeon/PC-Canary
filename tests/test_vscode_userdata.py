"""
Tests for evaluator.utils.vscode_userdata module
"""

import os
import tempfile
import shutil
import logging
from pathlib import Path

# Import the module to test
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from evaluator.utils.vscode_userdata import clear_vscode_user_storage


def test_clear_vscode_user_storage_dry_run():
    """Test that dry_run mode does not actually remove files/directories"""
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the expected VSCode storage structure
        session_storage = os.path.join(tmpdir, "Session Storage")
        local_storage = os.path.join(tmpdir, "Local Storage")
        cookies_file = os.path.join(tmpdir, "Cookies")
        cookies_journal = os.path.join(tmpdir, "Cookies-journal")
        
        os.makedirs(session_storage)
        os.makedirs(local_storage)
        Path(cookies_file).touch()
        Path(cookies_journal).touch()
        
        # Create a test file in Session Storage
        test_file = os.path.join(session_storage, "test.txt")
        with open(test_file, "w") as f:
            f.write("test data")
        
        # Setup logger
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        
        # Run cleanup in dry_run mode
        clear_vscode_user_storage(tmpdir, logger=logger, dry_run=True)
        
        # Verify that nothing was actually removed
        assert os.path.exists(session_storage), "Session Storage should still exist in dry_run"
        assert os.path.exists(local_storage), "Local Storage should still exist in dry_run"
        assert os.path.exists(cookies_file), "Cookies file should still exist in dry_run"
        assert os.path.exists(cookies_journal), "Cookies-journal should still exist in dry_run"
        assert os.path.exists(test_file), "Test file should still exist in dry_run"
        
        print("✓ Dry run test passed - no files were removed")


def test_clear_vscode_user_storage_actual_removal():
    """Test that the function actually removes the expected files and directories"""
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the expected VSCode storage structure
        session_storage = os.path.join(tmpdir, "Session Storage")
        local_storage = os.path.join(tmpdir, "Local Storage")
        cookies_file = os.path.join(tmpdir, "Cookies")
        cookies_journal = os.path.join(tmpdir, "Cookies-journal")
        
        os.makedirs(session_storage)
        os.makedirs(local_storage)
        Path(cookies_file).touch()
        Path(cookies_journal).touch()
        
        # Create a test file in Session Storage
        test_file = os.path.join(session_storage, "test.txt")
        with open(test_file, "w") as f:
            f.write("test data")
        
        # Create a file that should NOT be removed
        other_file = os.path.join(tmpdir, "other_file.txt")
        with open(other_file, "w") as f:
            f.write("should not be removed")
        
        # Setup logger
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        
        # Run cleanup without dry_run
        clear_vscode_user_storage(tmpdir, logger=logger, dry_run=False)
        
        # Verify that target files/directories were removed
        assert not os.path.exists(session_storage), "Session Storage should be removed"
        assert not os.path.exists(local_storage), "Local Storage should be removed"
        assert not os.path.exists(cookies_file), "Cookies file should be removed"
        assert not os.path.exists(cookies_journal), "Cookies-journal should be removed"
        
        # Verify that other files were NOT removed
        assert os.path.exists(other_file), "Other files should not be removed"
        
        print("✓ Actual removal test passed - only target files were removed")


def test_clear_vscode_user_storage_missing_targets():
    """Test that the function handles missing targets gracefully"""
    # Create a temporary directory with only some of the expected files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Only create Session Storage
        session_storage = os.path.join(tmpdir, "Session Storage")
        os.makedirs(session_storage)
        
        # Setup logger
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        
        # Run cleanup - should handle missing targets gracefully
        clear_vscode_user_storage(tmpdir, logger=logger, dry_run=False)
        
        # Verify Session Storage was removed
        assert not os.path.exists(session_storage), "Session Storage should be removed"
        
        print("✓ Missing targets test passed - function handled partial structure")


def test_clear_vscode_user_storage_error_handling():
    """Test that the function handles errors gracefully"""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a read-only directory to simulate a permission error
        protected_dir = os.path.join(tmpdir, "Session Storage")
        os.makedirs(protected_dir)
        
        # Create a file inside
        test_file = os.path.join(protected_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        
        # Make the file read-only
        os.chmod(test_file, 0o444)
        # Make the directory read-only (this may not prevent removal on all systems)
        os.chmod(protected_dir, 0o555)
        
        # Setup logger to capture warnings
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        
        # Run cleanup - should not raise exceptions
        try:
            clear_vscode_user_storage(tmpdir, logger=logger, dry_run=False)
            # If we get here, error handling worked
            print("✓ Error handling test passed - no exceptions raised")
        except Exception as e:
            # Cleanup permissions for proper temp dir removal
            os.chmod(protected_dir, 0o755)
            os.chmod(test_file, 0o644)
            raise AssertionError(f"Function should not raise exceptions, but got: {e}")
        finally:
            # Cleanup permissions for proper temp dir removal
            try:
                os.chmod(test_file, 0o644)
                os.chmod(protected_dir, 0o755)
            except:
                pass


def test_clear_vscode_user_storage_no_logger():
    """Test that the function works without a logger"""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple structure
        session_storage = os.path.join(tmpdir, "Session Storage")
        os.makedirs(session_storage)
        
        # Run cleanup without a logger
        clear_vscode_user_storage(tmpdir, logger=None, dry_run=False)
        
        # Verify it was removed
        assert not os.path.exists(session_storage), "Session Storage should be removed"
        
        print("✓ No logger test passed - function works without logger")


if __name__ == "__main__":
    # Run all tests
    print("Running VSCode userdata tests...\n")
    
    test_clear_vscode_user_storage_dry_run()
    test_clear_vscode_user_storage_actual_removal()
    test_clear_vscode_user_storage_missing_targets()
    test_clear_vscode_user_storage_error_handling()
    test_clear_vscode_user_storage_no_logger()
    
    print("\n✓ All tests passed!")
