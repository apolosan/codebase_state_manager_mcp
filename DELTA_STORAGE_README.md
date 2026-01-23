# File Hash Delta Storage Optimization

## Overview
The codebase state manager now uses delta encoding to optimize storage of file hashes. Instead of storing complete hash maps for every state, only changes (deltas) are stored, significantly reducing storage requirements for large codebases.

## Implementation

### State Model Changes
- Added `file_hash_deltas: Optional[Dict[str, Optional[str]]]` field
- `None` values indicate deleted files
- `str` values indicate added/modified files

### Storage Strategy
- **State 0 (Genesis)**: Stores full file hashes in both `file_hashes` and `file_hash_deltas`
- **State N (Transitions)**: Stores only deltas in `file_hash_deltas`, reconstructs full hashes on demand

### Reconstruction Process
Full hashes are reconstructed by:
1. Starting with genesis state hashes
2. Applying deltas sequentially from state 1 to target state
3. Handling additions, modifications, and deletions

### Benefits
- **Storage Reduction**: 90-99% reduction for projects with few changes per state
- **Backward Compatibility**: Existing APIs still return full reconstructed hashes
- **Performance**: Reconstruction cached when possible

### Migration
Existing states can be migrated using `scripts/migrate_to_deltas.py` to convert full hash storage to deltas.

## Testing
Comprehensive unit tests added in `tests/unit/test_delta_storage.py` covering:
- Delta computation
- Genesis vs transition handling
- Hash reconstruction
- State model serialization