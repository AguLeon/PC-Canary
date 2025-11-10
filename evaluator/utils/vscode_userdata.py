"""
VSCode User Data Storage Cleanup Utility

This module provides functionality to safely clear VSCode session/local storage
and cookie files that can contain stale Socket.IO sessions.

WARNING: This is a DESTRUCTIVE operation. Only call this function when:
1. You explicitly intend to clear VSCode user data storage
2. The path points to a VSCode user_data_dir
3. The operator has opted in via configuration

This should only be used during context restoration when stale session data
needs to be cleared to avoid connection issues.
"""

import os
import shutil
import logging
from typing import Optional


def clear_vscode_user_storage(
    to_path: str,
    logger: Optional[logging.Logger] = None,
    dry_run: bool = False
) -> None:
    """
    Clear VSCode user storage files that may contain stale session data.
    
    This function removes specific subdirectories and files within the VSCode
    user_data_dir that are known to store session state, including:
    - Session Storage/
    - Local Storage/
    - Cookies file
    - Cookies-journal file
    
    Args:
        to_path: Path to the VSCode user_data_dir
        logger: Optional logger instance for logging operations
        dry_run: If True, only log what would be removed without actually removing
    
    Returns:
        None
    
    Raises:
        No exceptions are raised. All errors are caught and logged as warnings.
    
    Example:
        >>> clear_vscode_user_storage(
        ...     "/root/vscode_user_data_dir",
        ...     logger=my_logger,
        ...     dry_run=False
        ... )
    """
    # Define the specific paths to clear
    targets = [
        "Session Storage",
        "Local Storage",
        "Cookies",
        "Cookies-journal"
    ]
    
    if logger is None:
        # Create a basic logger if none provided
        logger = logging.getLogger(__name__)
    
    logger.info(
        f"VSCode storage cleanup: {'DRY RUN - ' if dry_run else ''}Starting cleanup in {to_path}"
    )
    
    for target in targets:
        target_path = os.path.join(to_path, target)
        
        # Check if the target exists
        if not os.path.exists(target_path):
            logger.debug(f"VSCode storage cleanup: {target} not found, skipping")
            continue
        
        try:
            if os.path.isdir(target_path):
                if dry_run:
                    logger.info(f"VSCode storage cleanup: Would remove directory: {target_path}")
                else:
                    shutil.rmtree(target_path)
                    logger.info(f"VSCode storage cleanup: Removed directory: {target_path}")
            elif os.path.isfile(target_path):
                if dry_run:
                    logger.info(f"VSCode storage cleanup: Would remove file: {target_path}")
                else:
                    os.remove(target_path)
                    logger.info(f"VSCode storage cleanup: Removed file: {target_path}")
            else:
                logger.warning(
                    f"VSCode storage cleanup: {target_path} is neither a file nor directory, skipping"
                )
        except Exception as e:
            logger.warning(
                f"VSCode storage cleanup: Failed to remove {target_path}: {str(e)}"
            )
    
    logger.info(
        f"VSCode storage cleanup: {'DRY RUN - ' if dry_run else ''}Cleanup completed"
    )
