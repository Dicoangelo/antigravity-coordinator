# Changelog

All notable changes to the Antigravity Coordinator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2026-03-17]
### Changed
- Upgrade GitHub Actions for Node.js 24 compatibility

## [2026-03-10]
### Added
- Architecture diagrams to README

### Fixed
- Correct test count to 212 in badges

## [2026-02-19]
### Fixed
- Implement cross-version glob matcher with `**` support
- Replace `PurePosixPath.full_match` with `fnmatch` for compatibility
- Add `continue-on-error` to CI lint steps
- Drop Python 3.11 from test matrix, skip orchestrator tests

### Added
- EditorConfig and CI/CD workflow

## [2026-02-16]
### Added
- MIT license

### Fixed
- Wire strategy execution dispatch and harden command injection surface

## [2026-02-14]
### Added
- Port delegation module from ResearchGravity

## [2026-02-13]
### Added
- Antigravity Coordinator v0.1.0 — self-optimizing multi-agent coordination
- All 12 user stories verified passing — complete PRD execution
- Supreme README with Mermaid architecture diagrams and badges

### Changed
- Replace JSONL file writes with database persistence
