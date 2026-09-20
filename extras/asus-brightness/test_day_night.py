"""Configuration contract tests; deployment also runs HA's configuration check."""
import json
import unittest
from pathlib import Path

import yaml


class SharedModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = yaml.safe_load(Path(__file__).with_name('day_night.yaml').read_text())
        rules = yaml.safe_load(Path(__file__).with_name('day_night_automations.yaml').read_text())
        cls.automations = {a['id']: a for a in rules}

    def test_helpers_restore_instead_of_forcing_initial_state(self):
        for helper in self.package['input_boolean'].values():
            self.assertNotIn('initial', helper)
        self.assertIn('day_night_next_boundary', self.package['input_datetime'])

    def test_schedule_uses_real_edges_not_unavailable_recovery(self):
        triggers = self.automations['shared_day_night_schedule']['triggers']
        edges = [(t['from'], t['to']) for t in triggers if t['trigger'] == 'state']
        self.assertEqual(edges, [('off', 'on'), ('on', 'off')])

    def test_schedule_startup_respects_saved_override_expiry(self):
        actions = self.automations['shared_day_night_schedule']['actions']
        decision = actions[1]['if'][0]['value_template']
        self.assertIn("trigger.id == 'edge'", decision)
        self.assertIn('input_boolean.day_night_initialized', decision)
        self.assertIn('input_datetime.day_night_next_boundary', decision)
        self.assertIn('as_timestamp(now()) >=', decision)
        self.assertFalse(actions[0]['continue_on_timeout'])

    def test_scripts_only_change_shared_helper(self):
        for script, action in [('day_mode', 'input_boolean.turn_off'),
                               ('night_mode', 'input_boolean.turn_on')]:
            sequence = self.package['script'][script]['sequence']
            self.assertEqual(len(sequence), 1)
            self.assertEqual(sequence[0]['action'], action)
            self.assertEqual(sequence[0]['target']['entity_id'], 'input_boolean.night_mode')

    def test_existing_buttons_feed_same_helper(self):
        rule = self.automations['shared_day_night_existing_buttons']
        self.assertEqual({t['topic'] for t in rule['triggers']}, {
            'smarthome/smarthome/global_1/day/set',
            'smarthome/smarthome/global_1/night/set'})
        self.assertTrue(all(t['payload'] == 'PRESS' for t in rule['triggers']))
        self.assertEqual(rule['actions'][0]['target']['entity_id'], 'input_boolean.night_mode')

    def test_display_reconnect_never_broadcasts(self):
        rule = self.automations['asus_display_brightness_schedule']
        self.assertEqual([a['action'] for a in rule['actions']], ['mqtt.publish'])
        self.assertNotIn('schedule.night_mode', json.dumps(rule))

    def test_brightness_uses_shared_mode_not_schedule(self):
        for name in ['shared_day_night_apply', 'asus_display_brightness_schedule']:
            rule = self.automations[name]
            data = rule['actions'][0]['data']
            self.assertEqual(data['topic'], 'wallpanel/asus/brightness/set')
            self.assertEqual(data['qos'], 1)
            self.assertTrue(data['retain'])
            self.assertIn("15 if is_state('input_boolean.night_mode', 'on') else 100", data['payload'])
            self.assertNotIn('schedule.night_mode', json.dumps(rule))

    def test_no_periodic_schedule_override(self):
        for rule in self.automations.values():
            self.assertTrue(all(t['trigger'] != 'time_pattern' for t in rule['triggers']))

    def test_apply_updates_display_before_waiting_for_hardware(self):
        rule = self.automations['shared_day_night_apply']
        self.assertEqual(rule['actions'][0]['action'], 'mqtt.publish')
        self.assertIn('wait_template', rule['actions'][1])
        self.assertFalse(rule['actions'][1]['continue_on_timeout'])
        self.assertEqual(rule['actions'][-1]['action'], 'button.press')
        self.assertEqual(rule['mode'], 'restart')


if __name__ == '__main__':
    unittest.main()
