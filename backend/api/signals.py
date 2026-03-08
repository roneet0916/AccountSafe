# api/signals.py
"""
Django signals for automatic model lifecycle management.

Handles:
- UserProfile auto-creation on User registration
- File cleanup on Profile deletion/update
- Storage quota enforcement (Operation: Iron Fist)
"""

import os
import logging
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import UserProfile, Profile, Organization


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# USER PROFILE AUTO-CREATION
# ═══════════════════════════════════════════════════════════════════════════════


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a UserProfile when a new User is created.
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Automatically save the UserProfile when the User is saved.
    """
    if hasattr(instance, "userprofile"):
        instance.userprofile.save()


# ═══════════════════════════════════════════════════════════════════════════════
# STORAGE QUOTA ENFORCEMENT (Operation: Iron Fist)
# Hard limit: 20MB per user. No exceptions.
# ═══════════════════════════════════════════════════════════════════════════════


def get_user_from_instance(instance):
    """Get the User object from various model instances."""
    if isinstance(instance, UserProfile):
        return instance.user
    elif isinstance(instance, Profile):
        return instance.organization.category.user
    elif isinstance(instance, Organization):
        return instance.category.user
    return None


def get_file_size(file_field):
    """Safely get file size, returning 0 if file doesn't exist."""
    if not file_field:
        return 0
    try:
        return file_field.size
    except (FileNotFoundError, ValueError, OSError):
        return 0


def check_storage_quota(user, new_file_size, old_file_size=0):
    """
    Check if upload would exceed storage quota.
    Raises ValidationError if quota would be exceeded.
    """
    if not user or not hasattr(user, "userprofile"):
        return

    profile = user.userprofile
    # Calculate net change (new file minus old file if replacing)
    net_change = new_file_size - old_file_size

    if net_change > 0:
        if (profile.storage_used + net_change) > profile.storage_limit:
            used_mb = profile.storage_used / (1024 * 1024)
            limit_mb = profile.storage_limit / (1024 * 1024)
            file_mb = new_file_size / (1024 * 1024)
            raise ValidationError(
                f"Storage quota exceeded! "
                f"You're using {used_mb:.1f}MB of {limit_mb:.0f}MB. "
                f"This file ({file_mb:.1f}MB) would exceed your limit. "
                f"Please delete some files first."
            )


# ---------------------------------------------------------------------------
# Profile Document Signals
# ---------------------------------------------------------------------------


@receiver(pre_save, sender=Profile)
def profile_pre_save_storage_check(sender, instance, **kwargs):
    """
    ENFORCER: Check storage quota BEFORE saving Profile document.
    Also handles old document cleanup.
    """
    old_file_size = 0
    new_file_size = get_file_size(instance.document)

    if instance.pk:
        try:
            old_profile = Profile.objects.get(pk=instance.pk)
            old_file_size = get_file_size(old_profile.document)

            # If document changed, delete old file
            if old_profile.document and old_profile.document != instance.document:
                try:
                    if os.path.isfile(old_profile.document.path):
                        os.remove(old_profile.document.path)
                except Exception as e:
                    logger.error(f"Error deleting old document: {e}")
        except Profile.DoesNotExist:
            pass

    # Check quota if new file is being uploaded
    if new_file_size > 0:
        user = get_user_from_instance(instance)
        check_storage_quota(user, new_file_size, old_file_size)


@receiver(post_save, sender=Profile)
def profile_post_save_update_storage(sender, instance, created, **kwargs):
    """
    Update storage counter after Profile document save.
    """
    user = get_user_from_instance(instance)
    if user and hasattr(user, "userprofile"):
        new_size = get_file_size(instance.document)
        if created and new_size > 0:
            user.userprofile.add_storage(new_size)


@receiver(pre_delete, sender=Profile)
def profile_pre_delete_cleanup(sender, instance, **kwargs):
    """
    Delete document file and update storage when Profile is deleted.
    """
    file_size = get_file_size(instance.document)

    # Delete file from disk
    if instance.document:
        try:
            if os.path.isfile(instance.document.path):
                os.remove(instance.document.path)
        except Exception as e:
            logger.error(f"Error deleting profile document: {e}")

    # Update storage counter
    if file_size > 0:
        user = get_user_from_instance(instance)
        if user and hasattr(user, "userprofile"):
            user.userprofile.subtract_storage(file_size)


# ---------------------------------------------------------------------------
# Organization Logo Signals
# ---------------------------------------------------------------------------


@receiver(pre_save, sender=Organization)
def organization_pre_save_storage_check(sender, instance, **kwargs):
    """
    Check storage quota before saving Organization logo.
    """
    old_file_size = 0
    new_file_size = get_file_size(instance.logo_image)

    if instance.pk:
        try:
            old_org = Organization.objects.get(pk=instance.pk)
            old_file_size = get_file_size(old_org.logo_image)

            # If logo changed, delete old file
            if old_org.logo_image and old_org.logo_image != instance.logo_image:
                try:
                    if os.path.isfile(old_org.logo_image.path):
                        os.remove(old_org.logo_image.path)
                except Exception as e:
                    logger.error(f"Error deleting old logo: {e}")
        except Organization.DoesNotExist:
            pass

    if new_file_size > 0:
        user = get_user_from_instance(instance)
        check_storage_quota(user, new_file_size, old_file_size)


@receiver(post_save, sender=Organization)
def organization_post_save_update_storage(sender, instance, created, **kwargs):
    """
    Update storage counter after Organization logo save.
    """
    user = get_user_from_instance(instance)
    if user and hasattr(user, "userprofile"):
        new_size = get_file_size(instance.logo_image)
        if created and new_size > 0:
            user.userprofile.add_storage(new_size)


@receiver(pre_delete, sender=Organization)
def organization_pre_delete_cleanup(sender, instance, **kwargs):
    """
    Delete logo file and update storage when Organization is deleted.
    """
    file_size = get_file_size(instance.logo_image)

    if instance.logo_image:
        try:
            if os.path.isfile(instance.logo_image.path):
                os.remove(instance.logo_image.path)
        except Exception as e:
            logger.error(f"Error deleting org logo: {e}")

    if file_size > 0:
        user = get_user_from_instance(instance)
        if user and hasattr(user, "userprofile"):
            user.userprofile.subtract_storage(file_size)


# ---------------------------------------------------------------------------
# UserProfile Picture Signals
# ---------------------------------------------------------------------------


@receiver(pre_save, sender=UserProfile)
def userprofile_pre_save_storage_check(sender, instance, **kwargs):
    """
    Check storage quota before saving profile picture.
    """
    old_file_size = 0
    new_file_size = get_file_size(instance.profile_picture)

    if instance.pk:
        try:
            old_profile = UserProfile.objects.get(pk=instance.pk)
            old_file_size = get_file_size(old_profile.profile_picture)

            # If picture changed, delete old file
            if old_profile.profile_picture and old_profile.profile_picture != instance.profile_picture:
                try:
                    if os.path.isfile(old_profile.profile_picture.path):
                        os.remove(old_profile.profile_picture.path)
                except Exception as e:
                    logger.error(f"Error deleting old profile picture: {e}")
        except UserProfile.DoesNotExist:
            pass

    if new_file_size > 0:
        check_storage_quota(instance.user, new_file_size, old_file_size)
