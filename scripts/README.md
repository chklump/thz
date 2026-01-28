# Scripts for THZ Integration

## clear_ha_entity_cache.sh

This script helps resolve entity naming issues by clearing Home Assistant's entity cache.

### Problem it Solves

When entity translation keys are updated in the integration, Home Assistant may cache old entity names in `/config/.storage/core.restore_state`. This causes entities to display as "THZ" instead of their translated names even after:
- Restarting Home Assistant
- Reloading the integration
- Removing and re-adding the integration

### What the Script Does

1. **Backs up** critical files:
   - `/config/.storage/core.restore_state` - Entity state cache
   - `/config/.storage/core.entity_registry` - Entity registry

2. **Clears the cache** by removing `core.restore_state`

3. **Saves backups** to `/config/backups/entity_cache_backup_TIMESTAMP/`

### Usage

#### Option 1: Inside Home Assistant Container (Docker)

```bash
docker exec -it homeassistant bash /config/custom_components/thz/scripts/clear_ha_entity_cache.sh
```

#### Option 2: Direct Access (Home Assistant OS / Supervised)

```bash
# SSH into Home Assistant
ssh root@homeassistant.local

# Run the script
bash /config/custom_components/thz/scripts/clear_ha_entity_cache.sh
```

#### Option 3: Using Home Assistant Terminal Add-on

1. Install the Terminal & SSH add-on
2. Open Terminal
3. Run:
```bash
bash /config/custom_components/thz/scripts/clear_ha_entity_cache.sh
```

### Alternative: Manual Steps

If you prefer to do this manually:

1. **Stop Home Assistant**
   ```bash
   ha core stop
   ```

2. **Backup the file**
   ```bash
   cp /config/.storage/core.restore_state /config/core.restore_state.backup
   ```

3. **Delete the cache**
   ```bash
   rm /config/.storage/core.restore_state
   ```

4. **Start Home Assistant**
   ```bash
   ha core start
   ```

5. **Remove and re-add THZ integration**
   - Go to Settings → Devices & Services
   - Find THZ integration
   - Click the 3 dots → Delete
   - Restart Home Assistant
   - Re-add the THZ integration

### What to Expect

After clearing the cache and re-adding the integration:
- ✅ Entities should display as "THZ Room Temperature Day HC1"
- ✅ Not just "THZ"
- ✅ Translation system will work correctly

### Troubleshooting

If entities still show as "THZ" after running this script:

1. **Verify translation files exist:**
   ```bash
   ls -la /config/custom_components/thz/strings.json
   ls -la /config/custom_components/thz/translations/
   ```

2. **Check Home Assistant logs** with debug enabled:
   ```yaml
   # configuration.yaml
   logger:
     logs:
       custom_components.thz: debug
       homeassistant.helpers.translation: debug
   ```

3. **Verify integration version:**
   - Make sure you're using the latest version with translation fixes
   - Check that commit `f02ff6a` or later is included

### Safety

- **The script creates backups** before deleting anything
- **Backups include timestamps** so you can identify which backup to restore
- **To restore from backup:**
  ```bash
  cp /config/backups/entity_cache_backup_TIMESTAMP/core.restore_state.backup /config/.storage/core.restore_state
  ```

### Notes

- Clearing `core.restore_state` will cause Home Assistant to forget the last state of all entities
- Entities will show as "Unknown" or "Unavailable" until they update
- This is normal and entities will recover their state within seconds/minutes
- The script is safe to run multiple times
