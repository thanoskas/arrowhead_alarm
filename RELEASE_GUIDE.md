# Release Guide for Version 2.0.0

This guide will help you release version 2.0.0 of the Arrowhead Alarm Panel integration to GitHub.

## 📋 Pre-Release Checklist

- [ ] All code tested and working
- [ ] Documentation updated (README.md)
- [ ] CHANGELOG.md updated with all changes
- [ ] Version number updated in manifest.json (2.0.0)
- [ ] All files organized in proper structure
- [ ] LICENSE file included
- [ ] .gitignore configured

## 🚀 Step-by-Step Release Process

### Step 1: Prepare Your Local Repository

```bash
# Navigate to your project directory
cd /path/to/arrowhead_alarm

# Make sure you're on the main branch
git checkout main

# Pull latest changes (if working with remote)
git pull origin main
```

### Step 2: Update Files in Your Repository

Copy the new version 2.0.0 files to your repository:

```bash
# Copy the entire custom_components directory
cp -r /path/to/v2/custom_components/arrowhead_alarm/* custom_components/arrowhead_alarm/

# Copy documentation files
cp /path/to/v2/README.md .
cp /path/to/v2/CHANGELOG.md .
cp /path/to/v2/LICENSE .
cp /path/to/v2/hacs.json .
cp /path/to/v2/.gitignore .
```

### Step 3: Verify File Structure

Your repository should look like this:

```
arrowhead_alarm/
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── README.md
├── hacs.json
└── custom_components/
    └── arrowhead_alarm/
        ├── __init__.py
        ├── alarm_control_panel.py
        ├── arrowhead_client.py
        ├── binary_sensor.py
        ├── button.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── manifest.json
        ├── services.yaml
        ├── strings.json
        ├── switch.py
        └── translations/
            └── en.json
```

### Step 4: Stage and Commit Changes

```bash
# Stage all changes
git add .

# Commit with descriptive message
git commit -m "Release version 2.0.0 - ECi-only with MODE 4 support

Major changes:
- ECi-only focus (ESX removed)
- MODE 4 protocol support for firmware 10.3.50+
- Individual area panels
- Improved zone detection
- Enhanced services and automation
- Bug fixes and improvements

See CHANGELOG.md for complete list of changes."
```

### Step 5: Create and Push Git Tag

```bash
# Create annotated tag for v2.0.0
git tag -a v2.0.0 -m "Version 2.0.0 - ECi Series with MODE 4 Support

Major release with ECi-only focus, MODE 4 protocol support,
individual area panels, and numerous improvements.

See CHANGELOG.md for full details."

# Push commits to remote
git push origin main

# Push tag to remote
git push origin v2.0.0
```

### Step 6: Create GitHub Release

1. **Go to GitHub Repository**:
   - Navigate to https://github.com/thanoskas/arrowhead_alarm

2. **Access Releases**:
   - Click on "Releases" in the right sidebar
   - Or go to: https://github.com/thanoskas/arrowhead_alarm/releases

3. **Create New Release**:
   - Click "Draft a new release"
   - Choose tag: Select `v2.0.0` from dropdown
   - Release title: `v2.0.0 - ECi Series with MODE 4 Support`

4. **Release Description**:
   Copy this content into the release notes:

```markdown
# Version 2.0.0 - ECi Series with MODE 4 Support

## 🎉 Major Release

This is a major release focusing exclusively on Arrowhead ECi Series panels with enhanced MODE 4 protocol support and numerous improvements.

## ⚠️ Breaking Changes

**ESX Support Removed**: This version only supports ECi Series panels. If you need ESX Elite-SX support, please use version 1.x.

**Manual Area Configuration**: Areas must now be manually specified during setup for better reliability.

## ✨ What's New

### MODE 4 Protocol (Firmware 10.3.50+)
- 🎯 Keypad alarm triggering (panic, fire, medical)
- 🎯 Enhanced area commands (ARMAREA, STAYAREA)
- 🎯 User tracking for arm/disarm actions
- 🎯 Better entry/exit delay reporting

### Area Management
- 🏠 Individual alarm panel entities per area
- 🏠 Separate monitoring and control
- 🏠 Main panel controlling all areas

### Zone Detection
- 🔍 Improved automatic zone detection
- 🔍 Sealed zone support
- 🔍 Better expander detection

### Services
- ⚡ Bulk arm/disarm multiple areas
- ⚡ Bulk zone bypass operations
- ⚡ Enhanced area-specific commands
- ⚡ Custom command support

### Improvements
- 🐛 Fixed sealed zone initialization
- 🐛 Improved switch platform reliability
- 🐛 Better connection management
- 🐛 Enhanced error handling

## 📥 Installation

### HACS (Recommended)
1. Add custom repository: `https://github.com/thanoskas/arrowhead_alarm`
2. Install "Arrowhead Alarm Panel"
3. Restart Home Assistant
4. Add integration via UI

### Manual
1. Download `Source code (zip)` below
2. Extract to `config/custom_components/arrowhead_alarm`
3. Restart Home Assistant
4. Add integration via UI

## 📚 Documentation

See [README.md](https://github.com/thanoskas/arrowhead_alarm/blob/main/README.md) for complete documentation.

See [CHANGELOG.md](https://github.com/thanoskas/arrowhead_alarm/blob/main/CHANGELOG.md) for detailed changes.

## 🧪 Tested On

- ✅ ECi F/W Ver. 10.3.51 (MODE 4 fully functional)
- ✅ ECi F/W Ver. 10.3.50 (MODE 4 supported)
- ✅ Home Assistant 2024.11+

## 🆘 Support

- Issues: [GitHub Issues](https://github.com/thanoskas/arrowhead_alarm/issues)
- Discussions: [GitHub Discussions](https://github.com/thanoskas/arrowhead_alarm/discussions)

## 💝 Support the Project

[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue.svg)](https://paypal.me/thanoskasolas)

---

**Full Changelog**: https://github.com/thanoskas/arrowhead_alarm/blob/main/CHANGELOG.md
```

5. **Attach Files (Optional)**:
   - You can optionally create a ZIP file of the integration for direct download
   - GitHub automatically provides source code archives

6. **Set as Latest Release**:
   - Check "Set as the latest release"
   - If this is a pre-release, check "This is a pre-release"

7. **Publish**:
   - Click "Publish release"

### Step 7: Verify Release

1. Check that release appears at: https://github.com/thanoskas/arrowhead_alarm/releases
2. Verify source code archives are generated
3. Test installation via HACS (if applicable)
4. Verify README displays correctly on GitHub

### Step 8: Update HACS (if integrated)

If your integration is registered with HACS default repository:

1. HACS automatically detects new releases via tags
2. Users will see update available in HACS
3. No additional action required

If using as custom repository:
- Users need to manually check for updates in HACS

## 📝 Post-Release Tasks

### Announce the Release

1. **Home Assistant Community**:
   - Post in relevant forum threads
   - Share in Greek HA community if applicable

2. **Social Media** (optional):
   - Share on Twitter/X with #HomeAssistant hashtag
   - Post in relevant Facebook groups
   - LinkedIn announcement for professional network

3. **Update Documentation**:
   - Update any external documentation
   - Update Smart Home Hellas website if applicable

### Monitor Feedback

1. Watch for issues on GitHub
2. Monitor discussions
3. Check HACS for any installation issues
4. Respond to community questions

## 🔄 Hotfix Process (if needed)

If critical bugs are found:

```bash
# Create hotfix branch
git checkout -b hotfix/2.0.1

# Make fixes
# ... edit files ...

# Commit
git commit -m "Fix critical bug in zone detection"

# Merge to main
git checkout main
git merge hotfix/2.0.1

# Create new tag
git tag -a v2.0.1 -m "Hotfix for zone detection"

# Push
git push origin main
git push origin v2.0.1

# Create new GitHub release
```

## 📊 Success Metrics

Track these metrics post-release:
- Number of downloads/installations
- GitHub stars/watchers
- Issues reported
- Community feedback
- HACS installation success rate

## 🎯 Next Steps

After successful v2.0.0 release:
1. Plan v2.1.0 features based on feedback
2. Monitor for compatibility issues
3. Update documentation as needed
4. Consider translations for other languages
5. Plan long-term roadmap

---

## Quick Command Reference

```bash
# Full release sequence
git add .
git commit -m "Release v2.0.0"
git tag -a v2.0.0 -m "Version 2.0.0"
git push origin main
git push origin v2.0.0

# View tags
git tag -l

# Delete tag (if mistake)
git tag -d v2.0.0
git push origin :refs/tags/v2.0.0

# Create release ZIP
cd custom_components
zip -r ../arrowhead_alarm-2.0.0.zip arrowhead_alarm/
```

---

**Good luck with the release! 🚀**
