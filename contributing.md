# Contributing to Arrowhead Alarm Panel Integration

Thank you for your interest in contributing to the Arrowhead Alarm Panel Integration! This document provides guidelines and information for contributors.

## Code of Conduct

This project adheres to a code of conduct based on respect, inclusivity, and collaboration. By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When creating a bug report, include:

**Required Information:**
- Home Assistant version
- Integration version
- Panel model and firmware version (if known)
- Python version
- Operating system

**Detailed Description:**
- Clear description of the issue
- Steps to reproduce the behavior
- Expected vs. actual behavior
- Screenshots or logs (remove sensitive information)

**Debug Logs:**
Enable debug logging and include relevant log entries:
```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.arrowhead_alarm: debug
```

### Suggesting Enhancements

Enhancement suggestions are welcome! Please provide:
- Clear description of the proposed feature
- Use case and rationale
- Implementation considerations (if known)
- Potential impact on existing functionality

### Code Contributions

#### Development Environment Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/arrowhead_alarm.git
   cd arrowhead_alarm
   ```

2. **Create Development Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

3. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

#### Coding Standards

**Python Style:**
- Follow PEP 8 style guidelines
- Use Black for code formatting
- Use isort for import sorting
- Maximum line length: 88 characters

**Code Quality:**
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes
- Include comprehensive error handling
- Add logging for important operations

**Example Function:**
```python
async def async_send_command(
    self, command: str, expect_response: bool = False
) -> Optional[str]:
    """Send command to alarm panel.
    
    Args:
        command: Command string to send
        expect_response: Whether to wait for response
        
    Returns:
        Response string if expect_response is True, None otherwise
        
    Raises:
        ConnectionError: If not connected to panel
        asyncio.TimeoutError: If response timeout occurs
    """
    if not self.is_connected:
        raise ConnectionError("Not connected to alarm panel")
        
    _LOGGER.debug("Sending command: %s", command)
    # Implementation...
```

#### Home Assistant Integration Standards

**Entity Guidelines:**
- Use appropriate device classes
- Provide comprehensive attributes
- Implement proper availability logic
- Follow naming conventions

**Configuration Flow:**
- Validate all user inputs
- Provide helpful error messages
- Support options flow for runtime changes
- Include connection testing

**Services:**
- Document all service parameters
- Validate service data
- Provide appropriate error handling
- Use descriptive service names

#### Testing

**Unit Tests:**
```bash
pytest tests/unit/
```

**Integration Tests:**
```bash
pytest tests/integration/
```

**Test Requirements:**
- Write tests for all new functionality
- Maintain or improve code coverage
- Test error conditions and edge cases
- Mock external dependencies appropriately

**Example Test:**
```python
async def test_alarm_arm_away_success(hass, mock_client):
    """Test successful arm away operation."""
    mock_client.arm_away.return_value = True
    
    coordinator = ArrowheadDataUpdateCoordinator(hass, mock_client)
    result = await coordinator.async_arm_away()
    
    assert result is True
    mock_client.arm_away.assert_called_once()
```

#### Documentation

**Code Documentation:**
- Document all public APIs
- Include examples in docstrings
- Explain complex algorithms or protocols
- Document configuration options

**User Documentation:**
- Update README.md for new features
- Include configuration examples
- Document new services or entities
- Add troubleshooting information

### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow coding standards
   - Add/update tests
   - Update documentation
   - Commit with descriptive messages

3. **Test Thoroughly**
   ```bash
   # Run all tests
   pytest
   
   # Run linting
   pre-commit run --all-files
   
   # Test with real hardware (if possible)
   ```

4. **Submit Pull Request**
   - Use descriptive title and description
   - Reference related issues
   - Include testing notes
   - Ensure CI passes

**Pull Request Template:**
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Tested with real hardware
- [ ] No new linting errors

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] No breaking changes (or properly documented)
```

### Specific Contribution Areas

#### Panel Support
**Adding New Panel Types:**
- Research panel protocol and capabilities
- Implement panel-specific client class
- Add configuration options
- Update documentation
- Test with real hardware

#### Zone Detection
**Improving ECi Detection:**
- Research additional program locations
- Implement new detection methods
- Add fallback mechanisms
- Test with various configurations

#### Protocol Enhancement
**Communication Improvements:**
- Analyze protocol specifications
- Implement new message types
- Add error recovery mechanisms
- Test edge cases

#### User Interface
**Configuration Flow Improvements:**
- Enhance user experience
- Add validation and error handling
- Improve help text and descriptions
- Support additional use cases

## Release Process

### Version Management
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Update version in manifest.json
- Create GitHub releases with release notes
- Tag releases appropriately

### Release Notes
Include in release notes:
- New features and improvements
- Bug fixes
- Breaking changes (with migration guide)
- Known issues

### Testing Before Release
- Test with multiple panel types
- Verify upgrade path from previous version
- Test fresh installation
- Validate HACS compatibility

## Getting Help

**Development Questions:**
- Check existing documentation
- Search closed issues and PRs
- Ask in GitHub Discussions
- Contact maintainers

**Testing Hardware:**
If you need help testing with specific hardware:
- Create issue describing your setup
- Provide panel model and firmware version
- Include configuration details
- Offer remote testing assistance

## Recognition

Contributors will be recognized in:
- README.md acknowledgments
- Release notes
- GitHub contributor statistics
- Documentation credits

## Contact

- **Issues**: [GitHub Issues](https://github.com/thanoskas/arrowhead_alarm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/thanoskas/arrowhead_alarm/discussions)
- **Email**: [Project maintainer](mailto:your-email@example.com)

---

Thank you for contributing to make this integration better for everyone!