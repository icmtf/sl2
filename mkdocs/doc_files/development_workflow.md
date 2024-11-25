# Development Workflow

This document describes the development workflow and branching strategy used in the CodeHorizon project.

## Branch Structure

The repository consists of two main branches:

1. `sbx01` (Sandbox)
2. `dev01` (Development)

### Sandbox Branch (sbx01)

The Sandbox branch is dedicated to active development and testing. Key characteristics:

- Primary branch for developers to work on new features and fixes
- Allows for rapid iteration and experimentation
- Code can be tested immediately
- May contain work-in-progress features
- Used for initial testing and validation

### Development Branch (dev01)

The Development branch contains code that has been reviewed and tested. Key characteristics:

- Contains merged and approved code from sbx01
- Changes are integrated through pull requests
- Hosts the development environment at <a href="http://inet-services.dev.echonet/" target="_blank">http://inet-services.dev.echonet/</a>
- Should be running continuously
- Serves as a stable integration environment

## Development Process

1. **Feature Development**
   - Create a feature branch from `sbx01`
   - Develop and test your changes
   - Commit changes with meaningful commit messages
   - Push changes to your feature branch

2. **Code Integration**
   - Merge latest `sbx01` changes into your feature branch
   - Resolve any conflicts
   - Test your changes thoroughly
   - Push final changes to your feature branch

3. **Pull Request Process**
   - Create a pull request from your feature branch to `sbx01`
   - Add relevant reviewers
   - Address review comments and make necessary changes
   - Get approval from reviewers
   - Merge into `sbx01`

4. **Promotion to Development**
   - Create a pull request from `sbx01` to `dev01`
   - Ensure all tests pass
   - Get final approval
   - Merge into `dev01`

## Best Practices

1. **Commit Messages**
   - Write clear, descriptive commit messages
   - Use conventional commit format when possible
   - Reference related issues/tickets

2. **Code Review**
   - Review code for quality and standards
   - Test functionality
   - Check for potential security issues
   - Verify documentation is updated

3. **Testing**
   - Write and update tests for new features
   - Ensure all tests pass before creating pull requests
   - Test in sandbox environment before promoting to development

4. **Documentation**
   - Update documentation for new features
   - Include API changes in documentation
   - Add comments for complex code sections

## Environment Management

### Sandbox Environment
- Used for active development
- May be unstable
- Refreshed frequently
- Used for feature testing

### Development Environment
- Available at <a href="http://inet-services.dev.echonet/" target="_blank">http://inet-services.dev.echonet/</a>
- Must maintain stability
- Used for integration testing
- Regularly updated with new features
- Monitored for issues

## Continuous Integration

- [TODO] Automated tests run on pull requests
- [TODO] Code quality checks
- [TODO] Security scanning
- [IN PROGRESS] Docker image building and testing
- Documentation generation

## Emergency Fixes

For critical issues requiring immediate attention:

1. Create hotfix branch from `dev01`
2. Fix the issue
3. Create pull request directly to `dev01`
4. After merge to `dev01`, create pull request to `sbx01`

## Monitoring and Maintenance

- Regular monitoring of development environment
- Performance tracking
- Error logging and analysis
- Regular dependency updates
- Security patches implementation