#!/bin/bash
# Script to clear Home Assistant entity cache for THZ integration
# This helps force Home Assistant to reload entity names and translations

set -e

echo "================================================"
echo "Home Assistant Entity Cache Clearer for THZ"
echo "================================================"
echo ""

# Check if running with proper permissions
if [ ! -w "/config/.storage" ] 2>/dev/null; then
    echo "WARNING: Cannot write to /config/.storage"
    echo "This script should be run inside Home Assistant container or"
    echo "with appropriate permissions to access HA config directory."
    echo ""
    echo "If running in Docker, use:"
    echo "  docker exec -it homeassistant bash /config/custom_components/thz/scripts/clear_ha_entity_cache.sh"
    echo ""
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Define paths
STORAGE_DIR="/config/.storage"
RESTORE_STATE="$STORAGE_DIR/core.restore_state"
ENTITY_REGISTRY="$STORAGE_DIR/core.entity_registry"
BACKUP_DIR="/config/backups/entity_cache_backup_$(date +%Y%m%d_%H%M%S)"

echo "Step 1: Creating backup directory..."
mkdir -p "$BACKUP_DIR"
echo "Backup directory: $BACKUP_DIR"
echo ""

# Backup core.restore_state
if [ -f "$RESTORE_STATE" ]; then
    echo "Step 2: Backing up core.restore_state..."
    cp "$RESTORE_STATE" "$BACKUP_DIR/core.restore_state.backup"
    echo "✓ Backed up to: $BACKUP_DIR/core.restore_state.backup"
    
    # Show file size
    SIZE=$(du -h "$RESTORE_STATE" | cut -f1)
    echo "  File size: $SIZE"
else
    echo "Step 2: core.restore_state not found (this is OK if HA is new)"
fi
echo ""

# Backup entity registry
if [ -f "$ENTITY_REGISTRY" ]; then
    echo "Step 3: Backing up core.entity_registry..."
    cp "$ENTITY_REGISTRY" "$BACKUP_DIR/core.entity_registry.backup"
    echo "✓ Backed up to: $BACKUP_DIR/core.entity_registry.backup"
    
    SIZE=$(du -h "$ENTITY_REGISTRY" | cut -f1)
    echo "  File size: $SIZE"
else
    echo "Step 3: core.entity_registry not found"
fi
echo ""

echo "================================================"
echo "IMPORTANT: Home Assistant must be stopped before clearing cache!"
echo "================================================"
echo ""
echo "To clear the cache, you need to:"
echo "1. Stop Home Assistant"
echo "2. Delete $RESTORE_STATE"
echo "3. (Optional) Delete THZ entities from $ENTITY_REGISTRY"
echo "4. Start Home Assistant"
echo "5. Re-add the THZ integration"
echo ""
read -p "Do you want this script to attempt the deletion now? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "No files were deleted. Backups are saved in:"
    echo "$BACKUP_DIR"
    echo ""
    echo "To manually clear cache:"
    echo "  rm $RESTORE_STATE"
    echo ""
    exit 0
fi

echo ""
echo "Step 4: Clearing cache files..."

# Remove restore state
if [ -f "$RESTORE_STATE" ]; then
    rm "$RESTORE_STATE"
    echo "✓ Deleted core.restore_state"
else
    echo "✓ core.restore_state already removed"
fi

echo ""
echo "================================================"
echo "Cache cleared successfully!"
echo "================================================"
echo ""
echo "Backups saved in: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "1. Start Home Assistant"
echo "2. Remove the THZ integration (Settings → Devices & Services → THZ → Delete)"
echo "3. Restart Home Assistant"
echo "4. Re-add the THZ integration"
echo ""
echo "The integration should now display translated entity names!"
echo ""
