import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
from ghostdata.setup import (save_settings, read_settings, configured_log_path,
                             enable_logging, logging_enabled, setup_status)
from ghostdata.cli import main


class SetupTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.data=self.root/'user data';self.game=self.root/'Hearthstone test é';self.game.mkdir()
        (self.game/'Hearthstone.exe').write_bytes(b'test')
        self.config=self.root/'Blizzard/Hearthstone/log.config'
        env=patch.dict(os.environ,{'LOCALAPPDATA':str(self.root),'PROGRAMFILES':str(self.root/'none'),
                                  'PROGRAMFILES(X86)':str(self.root/'none'),'GHOSTDATA_DATA_DIR':str(self.data)})
        env.start();self.addCleanup(env.stop)

    def test_settings_and_custom_path_survive_restart(self):
        save_settings(self.game,self.data,acknowledge=True)
        self.assertEqual(configured_log_path(self.data),self.game/'Logs')
        self.assertTrue(read_settings(self.data)['setup_seen'])
        save_settings(self.game,self.data)
        self.assertTrue(read_settings(self.data)['setup_seen'])

    def test_empty_path_restores_auto_discovery(self):
        save_settings(self.game,self.data);save_settings('',self.data)
        self.assertIsNone(configured_log_path(self.data))

    def test_invalid_folder_preserves_previous_settings(self):
        save_settings(self.game,self.data)
        original=(self.data/'settings.json').read_bytes()
        with self.assertRaises(ValueError):save_settings(self.root/'no-game',self.data)
        self.assertEqual((self.data/'settings.json').read_bytes(),original)

    def test_corrupt_settings_fail_closed_and_explicit_save_backs_up(self):
        self.data.mkdir();(self.data/'settings.json').write_bytes(b'broken')
        with self.assertRaises(ValueError):configured_log_path(self.data)
        save_settings(self.game,self.data)
        self.assertEqual(next(self.data.glob('settings-invalid-*.bak')).read_bytes(),b'broken')
        self.assertEqual(configured_log_path(self.data),self.game/'Logs')

    def test_enabling_new_logging_is_idempotent(self):
        enable_logging(self.config);first=self.config.read_bytes()
        self.assertTrue(logging_enabled(self.config))
        enable_logging(self.config)
        self.assertEqual(self.config.read_bytes(),first)
        self.assertEqual(list(self.config.parent.glob('*.bak')),[])

    def test_logging_preserves_unrelated_sections_comments_bom_and_backup(self):
        original=b'\xef\xbb\xbf# My config\r\n[Other]\r\nValue=keep\r\n[Power]\r\n# retained\r\nFilePrinting=false\r\nLogLevel=0\r\nScreenPrinting=false\r\n[End]\r\nValue=also-keep\r\n'
        self.config.parent.mkdir(parents=True);self.config.write_bytes(original)
        enable_logging(self.config)
        self.assertTrue(logging_enabled(self.config));self.assertTrue(self.config.read_bytes().startswith(b'\xef\xbb\xbf'))
        text=self.config.read_text(encoding='utf-8-sig')
        self.assertIn('[Other]\nValue=keep\n',text);self.assertIn('# retained\n',text)
        self.assertIn('[End]\nValue=also-keep\n',text)
        self.assertEqual(next(self.config.parent.glob('*.bak')).read_bytes(),original)

    def test_header_without_trailing_newline_and_case_insensitive_section(self):
        self.config.parent.mkdir(parents=True);self.config.write_text('[power]')
        enable_logging(self.config);self.assertTrue(logging_enabled(self.config))

    def test_malformed_and_duplicate_config_is_never_replaced(self):
        self.config.parent.mkdir(parents=True)
        for content in ['bad config', '[Power]\nFilePrinting=true\nFilePrinting=false', '[Power]\n[power]']:
            self.config.write_text(content)
            with self.assertRaises(Exception):enable_logging(self.config)
            self.assertEqual(self.config.read_text(),content)

    def test_cli_uses_saved_path_for_recorder_and_tracker(self):
        save_settings(self.game,self.data)
        for flag,target in [('--record-once','record_once'),('--record-continuously','watch'),('--tracker-stream','run_tracker_stream')]:
            with patch('ghostdata.cli.'+target,return_value=(0,0)) as run,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([flag]),0)
                self.assertEqual(run.call_args.kwargs['power_log'],self.game/'Logs')

    def test_explicit_log_path_takes_precedence(self):
        save_settings(self.game,self.data)
        with patch('ghostdata.cli.record_once',return_value=(0,0)) as run,contextlib.redirect_stdout(io.StringIO()):
            main(['--record-once','--power-log',str(self.root/'Power.log')])
            self.assertEqual(run.call_args.kwargs['power_log'],self.root/'Power.log')

    def test_status_missing_sensor_and_data_never_reports_ready(self):
        result=setup_status(self.root,self.data)
        self.assertFalse(result['ready'])
        self.assertIn('ACTION NEEDED',[c['status'] for c in result['checks']])
        self.assertFalse(self.config.exists())  # diagnostics do not alter Blizzard config

    def test_sensor_timeout_returns_actionable_status(self):
        exe=self.root/'sensor/bin/GhostData.Sensor.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'test')
        with patch('ghostdata.setup.subprocess.run',side_effect=subprocess.TimeoutExpired('sensor',5)):
            result=setup_status(self.root,self.data)
        self.assertEqual(next(c for c in result['checks'] if c['name']=='Sensor')['status'],'UNAVAILABLE')
        self.assertFalse(result['ready'])

    def test_matching_card_cache_required_for_readiness(self):
        save_settings(self.game,self.data);enable_logging(self.config)
        logs=self.game/'Logs/session';logs.mkdir(parents=True);(logs/'Power.log').write_text('sample')
        exe=self.root/'sensor/bin/GhostData.Sensor.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'test')
        health={'status':'READY','hearthstone_running':True,'hearthstone_build':'37.0.0.123'}
        cache=Mock(local_source=True,legality_current=True,build_number=123,cards={'a':1})
        cache.load_latest_cache.return_value=True
        with patch('ghostdata.setup.subprocess.run',return_value=Mock(returncode=0,stdout=json.dumps(health).encode())),patch('ghostdata.tracking.card_db.CardDatabase',return_value=cache):
            self.assertTrue(setup_status(self.root,self.data)['ready'])
            cache.build_number=122
            self.assertFalse(setup_status(self.root,self.data)['ready'])
            cache.build_number=123;cache.legality_current=False
            self.assertFalse(setup_status(self.root,self.data)['ready'])
