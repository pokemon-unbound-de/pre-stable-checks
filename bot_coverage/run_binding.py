"""Verify a proposed runner receipt; does not attest a runner's honesty."""
import re

SHA256 = re.compile(r'[0-9a-fA-F]{64}')


def inspect_binding(receipt, expected_run_id, scenario, rom_sha256, actual_artifacts):
    """Return reason codes only. expected_run_id must originate outside receipt."""
    if not isinstance(expected_run_id, str) or not expected_run_id.strip():
        raise ValueError('expected run id required')
    if receipt is None:
        return ['binding_missing']
    if not isinstance(receipt, dict) or type(receipt.get('schema')) is not int or receipt['schema'] != 1:
        return ['binding_invalid']
    reasons = []
    if receipt.get('run_id') != expected_run_id:
        reasons.append('binding_run_id_mismatch')
    if receipt.get('scenario') != scenario:
        reasons.append('binding_scenario_mismatch')
    bound_rom = receipt.get('launched_rom_sha256')
    if not isinstance(bound_rom, str) or not SHA256.fullmatch(bound_rom) or bound_rom.lower() != rom_sha256.lower():
        reasons.append('binding_rom_mismatch')
    recorded = receipt.get('artifacts')
    if not isinstance(recorded, dict) or not recorded:
        reasons.append('binding_artifacts_invalid')
        return reasons
    if set(recorded) != set(actual_artifacts):
        reasons.append('binding_artifact_set_mismatch')
    for name, digest in recorded.items():
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            reasons.append('binding_artifacts_invalid')
            break
        if name in actual_artifacts and digest.lower() != actual_artifacts[name].lower():
            reasons.append('binding_artifact_hash_mismatch')
            break
    return reasons
