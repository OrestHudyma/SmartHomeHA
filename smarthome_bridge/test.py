import sys
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
import threading
import unittest
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, str(Path(__file__).parent / 'app'))
import periphery
import nmea
from settings import Settings
from state_store import StateStore
from controller import Controller
from hardware_adapter import HardwareAdapter
from discovery import discovery_messages
from mqtt_bridge import MQTTBridge
import paho.mqtt.client as mqtt


def options(**kwargs):
    return dict(serial_port='/dev/serial/by-id/controller', devices=[
        {'type': 'boiler', 'id': '1', 'name': 'Boiler'},
        {'type': 'fito_lamp', 'id': '1', 'name': 'Grow light'},
        {'type': 'global', 'id': '1', 'name': 'Global controls'},
    ], **kwargs)


class SettingsTests(unittest.TestCase):
    def test_shipped_names_are_english_and_identity_is_stable(self):
        import yaml
        root = Path(__file__).parent
        config = yaml.safe_load((root / 'config.yaml').read_text(encoding='utf-8'))
        settings = Settings.from_dict(dict(config['options'], serial_port='/dev/ttyUSB0'))
        self.assertEqual([d.name for d in settings.devices],
                         ['Boiler', 'Grow light', 'Global controls'])
        messages = discovery_messages(settings)
        expected = {
            'smarthome_boiler_1_power': 'Power',
            'smarthome_boiler_1_enabled': 'Enabled',
            'smarthome_boiler_1_result': 'Command result',
            'smarthome_fito_lamp_1_power': 'Power',
            'smarthome_fito_lamp_1_fast_on': 'Fast on',
            'smarthome_fito_lamp_1_fast_off': 'Fast off',
            'smarthome_fito_lamp_1_result': 'Command result',
            'smarthome_global_1_day': 'Day',
            'smarthome_global_1_night': 'Night',
            'smarthome_global_1_result': 'Command result',
            'smarthome_controller': 'USB controller',
        }
        self.assertEqual({m['unique_id']: m['name'] for m in messages.values()}, expected)
        self.assertEqual(set(messages), set(discovery_messages(Settings.from_dict(options()))))
        for message in messages.values():
            self.assertTrue(message['device']['name'].isascii())
        labels = yaml.safe_load((root / 'translations/en.yaml').read_text(encoding='utf-8'))
        for field in labels['configuration'].values():
            self.assertTrue(all(value.isascii() for value in field.values()))

    def test_defaults_and_multiple_lamps(self):
        data = options()
        data['devices'].append({'type': 'fito_lamp', 'id': '2', 'name': 'Grow light 2'})
        config = Settings.from_dict(data)
        self.assertEqual(config.devices[-1].key, 'fito_lamp_2')
        self.assertEqual(config.refresh_seconds, 3600)

    def test_rejects_invalid_options(self):
        cases = [dict(serial_port=''), dict(serial_port='/dev/../etc/passwd'),
                 dict(bridge_id='bad/+/id'), dict(mqtt_port=True), dict(refresh_seconds=0),
                 dict(mqtt_password=123), dict(log_level='bad'), dict(devices=[])]
        for update in cases:
            with self.subTest(update=update), self.assertRaises(ValueError):
                Settings.from_dict(dict(options(), **update))

    def test_rejects_unknown_duplicate_and_unaddressed_devices(self):
        for device in ({'type': 'fan', 'id': '1', 'name': 'Fan'},
                       {'type': 'fito_lamp', 'id': 'x,ON', 'name': 'Lamp'},
                       {'type': 'fito_lamp', 'id': 2, 'name': 'Lamp'},
                       {'type': 'boiler', 'id': '2', 'name': 'Second'},
                       {'type': 'fito_lamp', 'id': '1', 'name': 'Duplicate'}):
            data = options()
            data['devices'].append(device)
            with self.subTest(device=device), self.assertRaises(ValueError):
                Settings.from_dict(data)


class StateStoreTests(unittest.TestCase):
    def test_interlock_survives_restart_without_storing_power(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            StateStore(path).set_enabled('boiler_1', False)
            restored = StateStore(path)
            self.assertFalse(restored.enabled('boiler_1'))
            self.assertNotIn('power', restored.data)

    def test_corrupt_state_does_not_silently_reenable_boiler(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text('{broken')
            with self.assertRaisesRegex(ValueError, 'restore a backup'):
                StateStore(path)

    def test_failed_atomic_write_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            store = StateStore(path)
            store.set_enabled('boiler_1', False)
            with patch('state_store.os.replace', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    store.set_enabled('boiler_1', True)
            self.assertFalse(StateStore(path).enabled('boiler_1'))
            self.assertFalse(store.enabled('boiler_1'))
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])


class SelectedHardwareTests(unittest.TestCase):
    def test_only_opens_selected_port_and_reuses_wire_protocol(self):
        port = MagicMock()
        port.readline.return_value = b'ok\r\n'
        factory = MagicMock(return_value=port)
        with patch('periphery.list_ports.comports') as scan:
            hardware = HardwareAdapter('/dev/serial/by-id/selected', factory)
        scan.assert_not_called()
        self.assertEqual(factory.call_args.args[0], '/dev/serial/by-id/selected')
        self.assertEqual(factory.call_args.kwargs['write_timeout'], 1)
        self.assertIs(HardwareAdapter.transmit_fm433, periphery.HWInterface.transmit_fm433)
        self.assertIs(HardwareAdapter.test, periphery.HWInterface.test)
        hardware.close()
        port.close.assert_called_once()

    def test_closes_port_on_handshake_error(self):
        for answer in (b'not ok\n', b'', b'\xff\n'):
            port = MagicMock()
            port.readline.return_value = answer
            with self.subTest(answer=answer), self.assertRaises((ConnectionError, ValueError)):
                HardwareAdapter('/dev/test', lambda *a, **kw: port)
            port.close.assert_called_once()


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = StateStore(Path(self.temp.name) / 'state.json')
        self.settings = Settings.from_dict(options())
        self.hardware = MagicMock()
        self.hardware.test.return_value = True
        self.hardware.transmit_fm433.return_value = 'ok'
        self.factory = MagicMock(return_value=self.hardware)
        self.publish = MagicMock(return_value=True)
        self.now = 0
        self.controller = Controller(self.settings, self.store, self.publish,
                                     self.factory, lambda: self.now)
        self.controller.network_changed(True)
        self.controller.tick()

    def command(self, key, action, payload):
        self.assertTrue(self.controller.submit(key, action, payload))
        self.controller.tick()

    def test_start_does_not_transmit_or_publish_initial_on(self):
        self.hardware.transmit_fm433.assert_not_called()
        self.assertIsNone(self.controller.states['boiler_1']['power'])
        self.publish.assert_any_call('smarthome/smarthome/boiler_1/power/state', 'None', True)

    def test_all_commands_match_firmware_frames(self):
        cases = [('boiler_1', 'power', 'ON', '$SHBCC,ON,*58\n'),
                 ('boiler_1', 'power', 'OFF', '$SHBCC,OFF,*16\n'),
                 ('fito_lamp_1', 'power', 'ON', '$SHFTL,ON,1,*59\n'),
                 ('fito_lamp_1', 'power', 'OFF', '$SHFTL,OFF,1,*17\n'),
                 ('fito_lamp_1', 'fast_on', 'PRESS', '$SHFTL,FON,1,*1F\n'),
                 ('fito_lamp_1', 'fast_off', 'PRESS', '$SHFTL,FOFF,1,*51\n'),
                 ('global_1', 'day', 'PRESS', nmea.compose('SHGLB', 'DAY')),
                 ('global_1', 'night', 'PRESS', nmea.compose('SHGLB', 'NIGHT'))]
        for key, action, payload, frame in cases:
            with self.subTest(action=action, payload=payload):
                self.command(key, action, payload)
                self.hardware.transmit_fm433.assert_called_with(frame)

    def test_enable_sends_no_power_command_and_disable_blocks_on(self):
        self.command('boiler_1', 'enabled', 'OFF')
        self.hardware.transmit_fm433.assert_called_once_with('$SHBCC,OFF,*16\n')
        self.assertFalse(self.store.enabled('boiler_1'))
        self.command('boiler_1', 'power', 'ON')
        self.hardware.transmit_fm433.assert_called_once()
        self.assertEqual(self.controller.states['boiler_1']['power'], 'OFF')
        self.command('boiler_1', 'enabled', 'ON')
        self.hardware.transmit_fm433.assert_called_once()
        self.assertTrue(self.store.enabled('boiler_1'))

    def test_disable_persists_even_if_power_off_fails(self):
        self.hardware.transmit_fm433.return_value = 'error'
        self.command('boiler_1', 'enabled', 'OFF')
        self.assertFalse(self.store.enabled('boiler_1'))
        self.assertIsNone(self.controller.states['boiler_1']['power'])
        self.assertEqual(self.controller.states['boiler_1']['result'], 'transmission failed')

    def test_failed_enable_save_does_not_release_interlock(self):
        self.command('boiler_1', 'enabled', 'OFF')
        with patch.object(self.store, 'set_enabled', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.command('boiler_1', 'enabled', 'ON')
        self.assertFalse(self.controller.states['boiler_1']['enabled'])

    def test_failed_lamp_command_does_not_publish_false_success(self):
        self.hardware.transmit_fm433.return_value = 'error'
        self.publish.reset_mock()
        self.command('fito_lamp_1', 'power', 'ON')
        self.assertIsNone(self.controller.states['fito_lamp_1']['power'])
        self.assertNotIn(call('smarthome/smarthome/fito_lamp_1/power/state', 'ON', True),
                         self.publish.call_args_list)
        self.hardware.close.assert_called_once()

    def test_serial_exception_marks_unavailable_and_recovers(self):
        self.hardware.transmit_fm433.side_effect = OSError('USB lost')
        self.command('boiler_1', 'power', 'ON')
        self.assertFalse(self.controller.ready)
        self.publish.assert_any_call('smarthome/smarthome/hardware', 'offline', True)
        self.hardware.transmit_fm433.side_effect = None
        self.now = 6
        self.controller.tick()
        self.assertTrue(self.controller.ready)
        self.assertEqual(self.factory.call_count, 2)
        self.hardware.transmit_fm433.assert_called_once()  # No replay after USB recovery.

    def test_disconnect_discards_queued_commands_and_refresh(self):
        self.command('boiler_1', 'power', 'ON')
        self.assertTrue(self.controller.submit('boiler_1', 'power', 'ON'))
        self.controller.network_changed(False)
        self.now = 4000
        self.controller.tick()
        self.controller.network_changed(True)
        self.controller.tick()
        self.now = 8000
        self.controller.tick()
        self.hardware.transmit_fm433.assert_called_once()

    def test_rejects_retained_invalid_offline_and_expired_commands(self):
        for args in [('boiler_1', 'power', 'ON', True), ('unknown', 'power', 'ON'),
                     ('boiler_1', 'power', 'TOGGLE'), ('boiler_1', 'oops', 'ON')]:
            self.assertFalse(self.controller.submit(*args))
        self.assertTrue(self.controller.submit('boiler_1', 'power', 'ON'))
        self.now = 11
        self.controller.tick()
        self.controller.network_changed(False)
        self.assertFalse(self.controller.submit('boiler_1', 'power', 'ON'))
        self.hardware.transmit_fm433.assert_not_called()

    def test_queue_has_a_limit(self):
        accepted = sum(self.controller.submit('boiler_1', 'power', 'ON') for _ in range(100))
        self.assertEqual(accepted, 32)

    def test_simultaneous_submissions_execute_on_one_hardware_thread(self):
        owners = []
        self.hardware.transmit_fm433.side_effect = lambda frame: owners.append(threading.get_ident()) or 'ok'
        threads = [threading.Thread(target=self.controller.submit,
                                    args=(key, 'power', 'OFF'))
                   for key in ('boiler_1', 'fito_lamp_1')]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.controller.tick()
        self.controller.tick()
        self.assertEqual(owners, [threading.get_ident()] * 2)

    def test_ha_offline_stops_refresh_and_does_not_restore_on(self):
        self.command('boiler_1', 'power', 'ON')
        self.controller.home_assistant_status(False)
        self.now = 4000
        self.controller.tick()
        self.controller.home_assistant_status(True)
        self.now = 8000
        self.controller.tick()
        self.hardware.transmit_fm433.assert_called_once()

    def test_ha_offline_rejects_commands_until_online(self):
        self.assertTrue(self.controller.submit('boiler_1', 'power', 'ON'))
        self.controller.home_assistant_status(False)
        self.controller.tick()
        self.assertFalse(self.controller.submit('boiler_1', 'power', 'ON'))
        self.hardware.transmit_fm433.assert_not_called()
        self.controller.home_assistant_status(True)
        self.controller.tick()
        self.hardware.transmit_fm433.assert_not_called()
        self.command('boiler_1', 'power', 'OFF')
        self.hardware.transmit_fm433.assert_called_once()

    def test_refresh_only_for_initialized_devices(self):
        self.now = 3601
        self.controller.tick()
        self.hardware.transmit_fm433.assert_not_called()
        self.command('boiler_1', 'power', 'OFF')
        self.now = 7202
        self.controller.tick()
        self.assertEqual(self.hardware.transmit_fm433.call_args_list,
                         [call('$SHBCC,OFF,*16\n'), call('$SHBCC,OFF,*16\n')])

    def test_lamp_refresh_repeats_power_not_fast_commands(self):
        for action, payload, power in [('power', 'ON', 'ON'), ('power', 'OFF', 'OFF'),
                                       ('fast_on', 'PRESS', 'ON'), ('fast_off', 'PRESS', 'OFF')]:
            with self.subTest(action=action, payload=payload):
                self.command('fito_lamp_1', action, payload)
                self.hardware.transmit_fm433.reset_mock()
                self.now = self.controller.next_refresh - 1
                self.controller.tick()
                self.hardware.transmit_fm433.assert_not_called()
                self.now += 1
                self.controller.tick()
                self.hardware.transmit_fm433.assert_called_once_with(
                    nmea.compose('SHFTL', power, ['1']))
                self.assertEqual(self.controller.states['fito_lamp_1']['power'], power)
                self.controller.tick()
                self.hardware.transmit_fm433.assert_called_once()

    def test_refresh_addresses_each_lamp_and_preserves_boiler(self):
        data = options()
        data['refresh_seconds'] = 60
        data['devices'].append({'type': 'fito_lamp', 'id': '2', 'name': 'Grow light 2'})
        self.controller = Controller(Settings.from_dict(data), self.store, self.publish,
                                     self.factory, lambda: self.now)
        self.controller.network_changed(True)
        self.controller.tick()
        self.command('boiler_1', 'power', 'ON')
        self.command('fito_lamp_1', 'power', 'OFF')
        self.command('fito_lamp_2', 'power', 'ON')
        self.hardware.transmit_fm433.reset_mock()
        self.now = 60
        self.controller.tick()
        self.assertEqual(self.hardware.transmit_fm433.call_args_list, [
            call(nmea.compose('SHBCC', 'ON')),
            call(nmea.compose('SHFTL', 'OFF', ['1'])),
            call(nmea.compose('SHFTL', 'ON', ['2']))])

    def test_lamp_refresh_stops_after_network_loss_and_recovery(self):
        for change in (self.controller.network_changed, self.controller.home_assistant_status):
            with self.subTest(change=change.__name__):
                self.command('fito_lamp_1', 'power', 'ON')
                self.hardware.transmit_fm433.reset_mock()
                change(False)
                self.now += 4000
                self.controller.tick()
                self.hardware.transmit_fm433.assert_not_called()
                change(True)
                self.controller.tick()
                self.now += 4000
                self.controller.tick()
                self.hardware.transmit_fm433.assert_not_called()
                self.assertIsNone(self.controller.states['fito_lamp_1']['power'])

    def test_lamp_refresh_failure_invalidates_state_without_replay(self):
        self.command('fito_lamp_1', 'power', 'ON')
        self.hardware.transmit_fm433.reset_mock()
        self.hardware.transmit_fm433.return_value = 'error'
        self.now = 3600
        self.controller.tick()
        self.hardware.transmit_fm433.assert_called_once()
        self.assertIsNone(self.controller.states['fito_lamp_1']['power'])
        self.assertFalse(self.controller.ready)
        self.hardware.close.assert_called_once()
        self.hardware.transmit_fm433.return_value = 'ok'
        self.now += 6
        self.controller.tick()
        self.now += 4000
        self.controller.tick()
        self.hardware.transmit_fm433.assert_called_once()

    def test_usb_health_checks_every_ten_minutes(self):
        self.hardware.test.reset_mock()
        for timestamp, expected in [(599, 0), (600, 1), (1199, 1), (1200, 2)]:
            with self.subTest(timestamp=timestamp):
                self.now = timestamp
                self.controller.tick()
                self.assertEqual(self.hardware.test.call_count, expected)
        self.hardware.transmit_fm433.assert_not_called()

    def test_usb_health_failure_retries_after_five_seconds(self):
        self.hardware.test.return_value = False
        self.now = 600
        self.controller.tick()
        self.assertFalse(self.controller.ready)
        self.hardware.close.assert_called_once()
        self.now = 604
        self.controller.tick()
        self.assertEqual(self.factory.call_count, 1)
        self.hardware.test.return_value = True
        self.now = 605
        self.controller.tick()
        self.assertEqual(self.factory.call_count, 2)
        self.assertTrue(self.controller.ready)
        self.hardware.test.reset_mock()
        self.now = 1204
        self.controller.tick()
        self.hardware.test.assert_not_called()
        self.now = 1205
        self.controller.tick()
        self.hardware.test.assert_called_once()
        self.hardware.transmit_fm433.assert_not_called()

    def test_usb_health_failure_prevents_lamp_refresh(self):
        self.command('fito_lamp_1', 'power', 'OFF')
        self.hardware.transmit_fm433.reset_mock()
        self.hardware.test.return_value = False
        self.now = 3600
        self.controller.tick()
        self.hardware.transmit_fm433.assert_not_called()
        self.assertIsNone(self.controller.states['fito_lamp_1']['power'])

    def test_global_command_invalidates_lamp_power(self):
        self.command('fito_lamp_1', 'power', 'ON')
        self.command('global_1', 'night', 'PRESS')
        self.assertIsNone(self.controller.states['fito_lamp_1']['power'])
        self.hardware.transmit_fm433.reset_mock()
        self.now = 3600
        self.controller.tick()
        self.hardware.transmit_fm433.assert_not_called()

    def test_shutdown_closes_port_without_power_commands(self):
        self.controller.close()
        self.hardware.close.assert_called_once()
        self.hardware.transmit_fm433.assert_not_called()
        self.publish.assert_any_call('smarthome/smarthome/availability', 'offline', True)

    def test_discovery_identity_survives_rename_and_commands_not_retained(self):
        before = discovery_messages(self.settings)
        data = options()
        data['devices'][0]['name'] = 'New name'
        after = discovery_messages(Settings.from_dict(data))
        self.assertEqual(set(before), set(after))
        for topic, payload in after.items():
            self.assertEqual(before[topic]['unique_id'], payload['unique_id'])
            if 'command_topic' in payload:
                self.assertFalse(payload['retain'])
        self.assertEqual(sum('/light/' in topic for topic in after), 1)
        self.assertEqual(sum('/button/' in topic for topic in after), 4)

    def test_removed_device_discovery_is_cleaned_up(self):
        stale = 'homeassistant/light/smarthome_fito_lamp_2_power/config'
        self.store.set_discovery_topics([stale])
        self.controller.resync.set()
        self.controller.tick()
        self.publish.assert_any_call(stale, '', True)

    def test_failed_discovery_removal_is_retried(self):
        stale = 'homeassistant/light/smarthome_fito_lamp_2_power/config'
        self.store.set_discovery_topics([stale])
        self.publish.side_effect = lambda topic, payload, retain: topic != stale
        self.controller.resync.set()
        self.controller.tick()
        self.assertIn(stale, self.store.data['discovery_topics'])
        self.assertTrue(self.controller.resync.is_set())
        self.publish.side_effect = None
        self.publish.reset_mock()
        self.controller.tick()
        self.publish.assert_any_call(stale, '', True)
        self.assertNotIn(stale, self.store.data['discovery_topics'])

    def test_ha_restart_republishes_without_hardware_commands(self):
        self.controller.resync.set()
        self.publish.reset_mock()
        self.controller.tick()
        self.assertTrue(any('/config' in c.args[0] for c in self.publish.call_args_list))
        self.hardware.transmit_fm433.assert_not_called()


@unittest.skipUnless(os.environ.get('MQTT_TEST_PORT'), 'Set MQTT_TEST_PORT for real Mosquitto tests')
class MQTTIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings.from_dict(options(bridge_id='test_' + uuid.uuid4().hex[:10]))
        self.host = os.environ.get('MQTT_TEST_HOST', '127.0.0.1')
        self.port = int(os.environ['MQTT_TEST_PORT'])
        self.hardware = MagicMock()
        self.hardware.test.return_value = True
        self.hardware.transmit_fm433.return_value = 'ok'
        self.bridge = MQTTBridge(self.settings, (self.host, self.port, '', ''))
        self.controller = Controller(self.settings, StateStore(Path(self.temp.name) / 'state.json'),
                                     self.bridge.publish, lambda port: self.hardware)
        self.messages = []
        self.condition = threading.Condition()
        self.observer = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        subscribed = threading.Event()
        self.observer.on_connect = lambda c, u, f, r, p: c.subscribe('#', qos=1)
        self.observer.on_subscribe = lambda *args: subscribed.set()
        self.observer.on_message = self.receive
        self.observer.connect(self.host, self.port, keepalive=5)
        self.observer.loop_start()
        self.addCleanup(self.stop_observer)
        self.assertTrue(subscribed.wait(5))
        self.stop = threading.Event()
        self.errors = []
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.bridge.start(self.controller)
        self.worker.start()
        self.addCleanup(self.stop_bridge)
        self.wait(lambda: self.controller.ready)
        self.wait(lambda: self.has('availability', 'online'))

    def work(self):
        try:
            while not self.stop.is_set():
                self.controller.tick()
                self.stop.wait(0.02)
        except BaseException as exc:
            self.errors.append(exc)

    def wait(self, predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.errors:
                raise self.errors[0]
            if predicate():
                return
            self.stop.wait(0.02)
        self.fail('Timed out waiting for MQTT integration condition')

    def receive(self, client, userdata, message):
        with self.condition:
            self.messages.append((message.topic, message.payload.decode()))

    def has(self, suffix, payload):
        with self.condition:
            return (f'{self.settings.prefix}/{suffix}', payload) in self.messages

    def send(self, suffix, payload, retain=False):
        self.observer.publish(f'{self.settings.prefix}/{suffix}', payload, qos=1,
                              retain=retain).wait_for_publish(5)

    def restart_bridge_connection(self):
        self.bridge = MQTTBridge(self.settings, (self.host, self.port, '', ''))
        self.controller.publish = self.bridge.publish
        self.bridge.start(self.controller)
        self.wait(lambda: self.controller.ready)

    def stop_bridge(self):
        self.stop.set()
        self.worker.join(5)
        self.controller.close()
        self.bridge.close()
        self.assertFalse(self.worker.is_alive())

    def stop_observer(self):
        self.observer.disconnect()
        self.observer.loop_stop()

    def test_command_round_trip_and_ha_restart_discovery(self):
        self.send('boiler_1/power/set', 'OFF')
        self.wait(lambda: self.has('boiler_1/power/state', 'OFF'))
        self.hardware.transmit_fm433.assert_called_with('$SHBCC,OFF,*16\n')
        with self.condition:
            self.messages.clear()
        self.observer.publish('homeassistant/status', 'online', qos=1).wait_for_publish(5)
        self.wait(lambda: any(self.settings.bridge_id in t and t.endswith('/config')
                             for t, p in self.messages))
        self.hardware.transmit_fm433.assert_called_once()

    def test_retained_on_is_rejected_live_and_on_resubscribe(self):
        self.send('boiler_1/power/set', 'ON', retain=True)
        self.bridge.close()
        self.wait(lambda: not self.controller.connected)
        self.restart_bridge_connection()
        self.send('boiler_1/power/set', 'OFF')
        self.wait(lambda: self.has('boiler_1/power/state', 'OFF'))
        self.assertTrue(all(c.args[0] != '$SHBCC,ON,*58\n'
                            for c in self.hardware.transmit_fm433.call_args_list))

    def test_no_offline_command_replay(self):
        self.bridge.close()
        self.wait(lambda: not self.controller.connected)
        self.send('boiler_1/power/set', 'ON')
        self.restart_bridge_connection()
        self.send('boiler_1/power/set', 'OFF')
        self.wait(lambda: self.has('boiler_1/power/state', 'OFF'))
        self.assertTrue(all(c.args[0] != '$SHBCC,ON,*58\n'
                            for c in self.hardware.transmit_fm433.call_args_list))

    def test_ungraceful_disconnect_publishes_last_will(self):
        # A second client with the same ID forces the broker to close the first connection.
        generation = self.controller.generation
        with self.condition:
            self.messages.clear()
        intruder = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                               client_id=f'smarthome_{self.settings.bridge_id}', protocol=mqtt.MQTTv5)
        try:
            intruder.connect(self.host, self.port)
            intruder.loop_start()
            self.wait(lambda: self.has('availability', 'offline'))
            self.wait(lambda: self.controller.generation > generation)
        finally:
            intruder.disconnect()
            intruder.loop_stop()
        self.wait(lambda: self.controller.ready, timeout=10)

    @unittest.skipUnless(os.name == 'posix', 'PTY integration runs in the Linux container and CI')
    def test_actual_process_with_serial_pty_and_sigterm(self):
        import pty
        import select
        import subprocess
        master, slave = pty.openpty()
        frames = []
        serial_stop = threading.Event()

        def emulate():
            buffer = b''
            while not serial_stop.is_set():
                readable, _, _ = select.select([master], [], [], 0.1)
                if not readable:
                    continue
                buffer += os.read(master, 4096)
                while b'\n' in buffer:
                    frame, buffer = buffer.split(b'\n', 1)
                    frames.append(frame + b'\n')
                    os.write(master, b'ok\r\n')

        emulator = threading.Thread(target=emulate, daemon=True)
        emulator.start()
        bridge_id = self.settings.bridge_id + '_pty'
        config = options(bridge_id=bridge_id, mqtt_host=self.host, mqtt_port=self.port)
        config['serial_port'] = os.ttyname(slave)
        path = Path(self.temp.name) / 'options.json'
        path.write_text(json.dumps(config), encoding='utf-8')
        process = subprocess.Popen([sys.executable, '-u', str(Path(__file__).parent / 'app/main.py'),
                                    '--options', str(path), '--state', str(path.with_name('pty-state.json'))],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            topic = f'smarthome/{bridge_id}'
            self.wait(lambda: (topic + '/hardware', 'online') in self.messages)
            self.assertTrue(all(frame.startswith(b'$SHHWI,') for frame in frames))
            self.observer.publish(topic + '/fito_lamp_1/power/set', 'OFF', qos=1).wait_for_publish(5)
            self.wait(lambda: (topic + '/fito_lamp_1/power/state', 'OFF') in self.messages)
            self.assertEqual(frames.count(b'$SHFTL,OFF,1,*17\n'), 3)
            process.terminate()
            output, _ = process.communicate(timeout=8)
            self.assertEqual(process.returncode, 0, output.decode())
            self.wait(lambda: (topic + '/availability', 'offline') in self.messages)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            serial_stop.set()
            emulator.join(2)
            os.close(slave)
            os.close(master)

class NmeaTests(unittest.TestCase):
    def test_checksum_matches_known_nmea_sentence(self):
        sentence = (
            '$GPGGA,123519,4807.038,N,01131.000,E,1,08,'
            '0.9,545.4,M,46.9,M,,*47'
        )

        self.assertEqual(nmea.checksum(sentence), '47')

    def test_add_checksum_appends_separator_and_checksum(self):
        sentence = '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,'

        self.assertEqual(nmea.add_checksum(sentence), sentence + '*47')

    def test_compose_formats_parameters_and_line_ending(self):
        sentence = nmea.compose('SHFTL', 'ON', ['1'])

        self.assertEqual(sentence, nmea.add_checksum('$SHFTL,ON,1,') + '\n')

    def test_boiler_wire_frames_match_firmware_contract(self):
        self.assertEqual(nmea.compose('SHBCC', 'ON'), '$SHBCC,ON,*58\n')
        self.assertEqual(nmea.compose('SHBCC', 'OFF'), '$SHBCC,OFF,*16\n')

    def test_fito_lamp_wire_frames_match_firmware_contract(self):
        self.assertEqual(
            nmea.compose('SHFTL', 'ON', ['1']),
            '$SHFTL,ON,1,*59\n',
        )
        self.assertEqual(
            nmea.compose('SHFTL', 'OFF', ['1']),
            '$SHFTL,OFF,1,*17\n',
        )
        self.assertEqual(
            nmea.compose('SHFTL', 'FON', ['1']),
            '$SHFTL,FON,1,*1F\n',
        )
        self.assertEqual(
            nmea.compose('SHFTL', 'FOFF', ['1']),
            '$SHFTL,FOFF,1,*51\n',
        )


class BoilerTests(unittest.TestCase):
    def setUp(self):
        self.interface = MagicMock()
        self.interface.transmit_fm433.return_value = 'ok'
        self.boiler = periphery.Boiler(self.interface)

    def test_power_off_updates_state_and_sends_command(self):
        response = self.boiler.power_off()

        self.assertFalse(self.boiler.power)
        self.assertEqual(response, 'ok')
        self.interface.transmit_fm433.assert_called_once_with(
            nmea.compose('SHBCC', 'OFF')
        )

    def test_power_off_keeps_state_when_transmission_fails(self):
        self.interface.transmit_fm433.return_value = 'error'

        response = self.boiler.power_off()

        self.assertTrue(self.boiler.power)
        self.assertEqual(response, 'error')

    def test_power_on_sends_command_when_enabled(self):
        self.boiler.power = False

        response = self.boiler.power_on()

        self.assertTrue(self.boiler.power)
        self.assertEqual(response, 'ok')
        self.interface.transmit_fm433.assert_called_once_with(
            nmea.compose('SHBCC', 'ON')
        )

    def test_power_on_keeps_state_when_transmission_fails(self):
        self.boiler.power = False
        self.interface.transmit_fm433.return_value = 'error'

        response = self.boiler.power_on()

        self.assertFalse(self.boiler.power)
        self.assertEqual(response, 'error')

    def test_power_on_does_not_send_command_when_disabled(self):
        self.boiler.power = False
        self.boiler.enabled = False

        response = self.boiler.power_on()

        self.assertFalse(self.boiler.power)
        self.assertEqual(response, 'Cannot complete. Boiler disabled.')
        self.interface.transmit_fm433.assert_not_called()


class FitoLampTests(unittest.TestCase):
    def test_fast_power_commands_include_device_id(self):
        interface = MagicMock()
        interface.transmit_fm433.return_value = 'ok'
        lamp = periphery.FitoLamp(interface, '7')

        lamp.power_off_fast()
        lamp.power_on_fast()

        self.assertTrue(lamp.power)
        self.assertEqual(
            interface.transmit_fm433.call_args_list,
            [
                call(nmea.compose('SHFTL', 'FOFF', ['7'])),
                call(nmea.compose('SHFTL', 'FON', ['7'])),
            ],
        )


class HWInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.previous_class_port = periphery.HWInterface.com_port
        periphery.HWInterface.com_port = None

    def tearDown(self):
        periphery.HWInterface.com_port = self.previous_class_port

    @patch.object(periphery.HWInterface, 'test', side_effect=[False, True])
    @patch('periphery.serial.Serial')
    @patch('periphery.list_ports.comports')
    def test_selects_matching_port_and_closes_rejected_port(
        self,
        comports,
        serial_port,
        test_port,
    ):
        comports.return_value = [
            ('COM1', 'First port', 'HWID1'),
            ('COM2', 'Second port', 'HWID2'),
        ]
        rejected_port = MagicMock()
        matching_port = MagicMock()
        serial_port.side_effect = [rejected_port, matching_port]

        interface = periphery.HWInterface()

        self.assertIs(interface.com_port, matching_port)
        rejected_port.close.assert_called_once_with()
        matching_port.close.assert_not_called()
        self.assertEqual(test_port.call_count, 2)

    @patch.object(periphery.HWInterface, 'test', return_value=True)
    @patch('periphery.serial.Serial')
    @patch('periphery.list_ports.comports')
    def test_continues_after_port_open_error(
        self,
        comports,
        serial_port,
        test_port,
    ):
        comports.return_value = [
            ('COM1', 'Busy port', 'HWID1'),
            ('COM2', 'Matching port', 'HWID2'),
        ]
        matching_port = MagicMock()
        serial_port.side_effect = [
            periphery.serial.SerialException('Port is busy'),
            matching_port,
        ]

        interface = periphery.HWInterface()

        self.assertIs(interface.com_port, matching_port)
        test_port.assert_called_once_with(matching_port)
        matching_port.close.assert_not_called()

    @patch.object(periphery.HWInterface, 'test', return_value=False)
    @patch('periphery.serial.Serial')
    @patch('periphery.list_ports.comports')
    def test_closes_port_when_no_hardware_matches(
        self,
        comports,
        serial_port,
        _test_port,
    ):
        comports.return_value = [('COM1', 'Other device', 'HWID1')]
        rejected_port = MagicMock()
        serial_port.return_value = rejected_port

        interface = periphery.HWInterface()

        self.assertIsNone(interface.com_port)
        rejected_port.close.assert_called_once_with()

    def test_accepts_ok_response_with_crlf(self):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        serial_port = MagicMock()
        serial_port.readline.return_value = b'ok\r\n'

        result = interface.test(serial_port)

        self.assertTrue(result)
        serial_port.write.assert_called_once_with(
            (nmea.add_checksum('$SHHWI,test,') + '\n').encode()
        )

    def test_rejects_response_that_only_contains_ok(self):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        serial_port = MagicMock()
        serial_port.readline.return_value = b'not ok\r\n'

        self.assertFalse(interface.test(serial_port))

    @patch('periphery.time.sleep')
    def test_transmit_repeats_successful_command(self, sleep):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        interface.com_port = MagicMock()
        interface._transmit_lock = threading.Lock()
        interface.com_port.readline.side_effect = [b'ok\r\n'] * 3

        response = interface.transmit_fm433('payload')

        self.assertEqual(response, 'ok')
        self.assertEqual(
            interface.com_port.write.call_args_list,
            [call(b'payload')] * interface.FM433_REPEAT_COUNT,
        )
        self.assertEqual(sleep.call_count, interface.FM433_REPEAT_COUNT)

    @patch('periphery.time.sleep')
    def test_transmit_stops_on_first_error(self, sleep):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        interface.com_port = MagicMock()
        interface._transmit_lock = threading.Lock()
        interface.com_port.readline.side_effect = [b'ok\r\n', b'error\r\n']

        response = interface.transmit_fm433('payload')

        self.assertEqual(response, 'error')
        self.assertEqual(interface.com_port.write.call_count, 2)
        sleep.assert_called_once_with(interface.FM433_REPEAT_DELAY)

    @patch('periphery.time.sleep')
    def test_transmit_holds_lock_for_entire_command(self, _sleep):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        interface.com_port = MagicMock()
        interface.com_port.readline.side_effect = [b'ok\r\n'] * 3
        interface._transmit_lock = MagicMock()

        self.assertEqual(interface.transmit_fm433('payload'), 'ok')

        interface._transmit_lock.__enter__.assert_called_once_with()
        interface._transmit_lock.__exit__.assert_called_once()



if __name__ == '__main__':
    unittest.main()
