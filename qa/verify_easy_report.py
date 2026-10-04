import argparse
import hashlib
import json
import math
from pathlib import Path


def validate(result, expected_horizontal_speed=0.38, expected_vertical_speed=0.22, minimum_steady_state_cruise=0.0, expected_mcheli_sha256=None):
    assert math.isfinite(expected_horizontal_speed) and expected_horizontal_speed > 0, 'Expected horizontal speed must be positive and finite'
    assert math.isfinite(expected_vertical_speed) and expected_vertical_speed > 0, 'Expected vertical speed must be positive and finite'
    assert math.isfinite(minimum_steady_state_cruise) and 0 <= minimum_steady_state_cruise <= expected_horizontal_speed, 'Minimum steady-state cruise is outside the expected speed range'
    if expected_mcheli_sha256 is not None:
        assert len(expected_mcheli_sha256) == 64 and result['mcheliSha256'].lower() == expected_mcheli_sha256.lower(), 'Native report MCHeli hash does not match the requested candidate'
    data = result['cases']['movement']['server']
    local = result['cases']['movement']['client']
    packets = data['packets']

    def samples(scene, name):
        values = [value for value in scene['samples'] if value['phase'] == name]
        assert values, 'Native scene samples absent: ' + name
        return values

    assert packets and all(value['pilot'] for value in packets), 'Actual pilot control traffic absent'
    for phase, field, expected in [('forward', 'forward', 1), ('back', 'forward', -1), ('left', 'strafe', -1), ('right', 'strafe', 1), ('lift', 'lift', 1), ('down', 'lift', -1)]:
        assert any(value['phase'] == phase and value[field] == expected and value['mode'] == 2 for value in packets), 'Native binding/packet missing: ' + phase
    assert samples(data, 'lift')[-1]['y'] - samples(data, 'before-arm')[-1]['y'] > 5, 'Space did not take off'
    for phase, axis, sign in [('forward', 'z', 1), ('back', 'z', -1), ('left', 'x', -1), ('right', 'x', 1)]:
        values = samples(data, phase)
        assert sign * (values[-1][axis] - values[0][axis]) > 5, 'Native movement failed: ' + phase
    cruise = samples(data, 'forward')[-3:]
    assert len(cruise) == 3, 'Native steady-state cruise samples absent'
    cruise_speeds = [math.hypot(value['vx'], value['vz']) for value in cruise]
    assert all(math.isfinite(value) for value in cruise_speeds), 'Native cruise samples are nonfinite'
    observed_cruise = min(cruise_speeds)
    assert observed_cruise >= minimum_steady_state_cruise, 'Native steady-state cruise below minimum: {:.3f} < {:.3f}'.format(observed_cruise, minimum_steady_state_cruise)
    for name in ['hover', 'hover-after-mouse', 'hover-after-knockback']:
        last = samples(data, name)[-1]
        assert math.hypot(last['vx'], last['vz']) < .015 and abs(last['vy']) < .015, 'Released input retains drift: ' + name
        assert abs(last['pitch']) < .1 and abs(last['roll']) < .1, 'Released input retains tilt: ' + name
    mouse = [value for value in local['cameras'] if value['phase'] == 'mouse']
    assert mouse and abs(mouse[-1]['yaw'] - mouse[0]['yaw']) > 1 and abs(mouse[-1]['pitch'] - mouse[0]['pitch']) > 1 and all(abs(value['roll']) < .01 for value in local['cameras']), 'Native independent mouse camera failed'
    focus = [value for value in packets if value['phase'] == 'focus-lost']
    assert focus, 'Focus-loss native traffic absent'
    deadline = min(value['tick'] for value in focus) + 5
    settled = [value for value in focus if value['tick'] >= deadline]
    assert settled and all(value['mode'] == 3 and value['forward'] == value['strafe'] == value['lift'] == 0 for value in settled), 'Focus loss retained active intents beyond 250 ms'
    focus_world = [value for value in samples(data, 'focus-lost') if value['tick'] >= deadline]
    assert focus_world and all(value['throttle'] == 0 for value in focus_world), 'Focus loss retained motor power beyond 250 ms'
    assert samples(data, 'focus-restored')[-1]['throttle'] == 0 and samples(data, 'after-drop')[-1]['throttle'] == 0, 'Focus/packet timeout rearmed without Space'
    dropped = [value for value in packets if value['discardedByTransport']]
    assert dropped, 'Packet-loss fixture not exercised'
    assert data['preexistingMomentumInjected'] and data['moves'], 'Native high-momentum fixture absent'
    assert all(math.hypot(value['requestedX'], value['requestedZ']) <= expected_horizontal_speed + .000001 and -.500001 <= value['requestedY'] <= expected_vertical_speed + .000001 and math.hypot(value['dx'], value['dz']) <= expected_horizontal_speed + .000001 for value in data['moves']), 'Actual native displacement exceeds bounded fuse sweep'
    assert not local['mountedAfterExit'] and not data['final']['controlled'] and data['final']['throttle'] == 0, 'Shift did not disconnect and stop native tablet control'
    fuse = result['cases']['fuse']['server']
    assert all(not value['dead'] and value['throttle'] == 0 for value in samples(fuse, 'ground-safe')), 'Grounded unarmed drone detonated'
    assert fuse['final']['dead'] and fuse['final']['z'] < 18.5 and fuse['targetHPAfter'] == fuse['targetHPBefore'], 'Nearer real wall did not stop fuse before distant tank'
    return {'nativePackets': len(packets), 'discardedPackets': len(dropped), 'nativeMoves': len(data['moves']), 'focusSettlementTicks': 5, 'expectedHorizontalSpeed': expected_horizontal_speed, 'expectedVerticalSpeed': expected_vertical_speed, 'minimumSteadyStateCruise': minimum_steady_state_cruise, 'observedSteadyStateCruise': observed_cruise, 'fuseStoppedAt': fuse['final']['z'], 'distantTankHP': fuse['targetHPAfter']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--expected-horizontal-speed', type=float, default=0.38)
    parser.add_argument('--expected-vertical-speed', type=float, default=0.22)
    parser.add_argument('--minimum-steady-state-cruise', type=float, default=0.0)
    parser.add_argument('--expected-mcheli-sha256')
    args = parser.parse_args()
    original = args.report.read_bytes()
    report = json.loads(original)
    evidence = validate(report, args.expected_horizontal_speed, args.expected_vertical_speed, args.minimum_steady_state_cruise, args.expected_mcheli_sha256)
    assert report['ownedProcessesStopped'], 'QA native processes remain active'
    acceptance = {'passed': True, 'originalReportSha256': hashlib.sha256(original).hexdigest(), 'verifierSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'mcheliSha256': report['mcheliSha256'], 'expectedMcheliSha256': args.expected_mcheli_sha256, 'instrumentedSha256': report['instrumentedSha256'], 'physicalDeviceTested': False, 'nativeInputPipelineTested': True, 'ownedProcessesStopped': True, 'evidence': evidence}
    target = args.report.with_name('acceptance.json')
    target.write_text(json.dumps(acceptance, indent=2), encoding='utf-8')
    print(json.dumps(acceptance, indent=2))
    print(str(target))
