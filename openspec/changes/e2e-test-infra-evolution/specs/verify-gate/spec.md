# Capability: verify-gate (delta)

## MODIFIED Requirements

### Requirement: VG-PIPELINE — Gate pipeline (handle_change_done)

The scope check step in the verify pipeline SHALL additionally call `profile.check_test_infra_usage(changed_files, project_path)` after existing scope checks. Any returned warning strings SHALL be logged at WARNING level with prefix `[TEST-INFRA]` and included in the scope check output. These warnings SHALL NOT be blocking — they SHALL NOT increment `verify_retry_count` and SHALL NOT prevent merge.

#### Scenario: Test infra advisory in scope check
- **WHEN** scope check runs and `check_test_infra_usage()` returns warnings
- **THEN** the warnings SHALL be logged as `[TEST-INFRA] <warning text>`
- **AND** the scope check SHALL still pass if no other blocking issues exist

#### Scenario: Profile without check_test_infra_usage
- **WHEN** scope check runs and the profile does not implement `check_test_infra_usage()`
- **THEN** no test infra warnings SHALL be emitted
- **AND** the scope check SHALL behave identically to current behavior
