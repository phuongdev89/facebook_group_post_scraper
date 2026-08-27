import os
import unittest
from src.utils.i18n import (
    tr,
    get_current_language,
    set_current_language,
    get_flag_svg_path,
    TRANSLATIONS,
    SUPPORTED_LANGUAGES,
)
from src.database.repository import seed_default_settings, get_all_settings, set_setting


class TestI18nSystem(unittest.TestCase):
    def setUp(self):
        set_current_language('vi')

    def tearDown(self):
        set_current_language('vi')

    def test_supported_languages(self):
        self.assertIn('vi', SUPPORTED_LANGUAGES)
        self.assertIn('en', SUPPORTED_LANGUAGES)

    def test_all_keys_exist_in_both_languages(self):
        vi_keys = set(TRANSLATIONS['vi'].keys())
        en_keys = set(TRANSLATIONS['en'].keys())
        
        missing_in_en = vi_keys - en_keys
        missing_in_vi = en_keys - vi_keys

        self.assertEqual(missing_in_en, set(), f'Keys missing in en: {missing_in_en}')
        self.assertEqual(missing_in_vi, set(), f'Keys missing in vi: {missing_in_vi}')

    def test_tr_translation_lookup(self):
        set_current_language('vi')
        self.assertEqual(tr('tab_group_posts'), '📁 Quét Nhóm (Group Posts)')
        self.assertEqual(tr('tab_settings'), '⚙️ Cấu Hình')

        set_current_language('en')
        self.assertEqual(tr('tab_group_posts'), '📁 Group Posts')
        self.assertEqual(tr('tab_settings'), '⚙️ Settings')

    def test_tr_formatting(self):
        set_current_language('vi')
        self.assertIn('1 / 5', tr('page_info', current=1, total=5, count=100))
        self.assertIn('100', tr('page_info', current=1, total=5, count=100))

        set_current_language('en')
        self.assertIn('1 / 5', tr('page_info', current=1, total=5, count=100))
        self.assertIn('100', tr('page_info', current=1, total=5, count=100))

    def test_flag_svg_paths_exist(self):
        vi_path = get_flag_svg_path('vi')
        us_path = get_flag_svg_path('us')
        en_path = get_flag_svg_path('en')

        self.assertTrue(os.path.exists(vi_path), f'VN flag does not exist at {vi_path}')
        self.assertTrue(os.path.exists(us_path), f'US flag does not exist at {us_path}')
        self.assertTrue(os.path.exists(en_path), f'EN flag does not exist at {en_path}')

    def test_changelog_en_exists(self):
        changelog_en_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'CHANGELOG.en.md')
        self.assertTrue(os.path.exists(changelog_en_path), 'CHANGELOG.en.md must exist')
        with open(changelog_en_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('[1.0.7]', content)
        self.assertIn('[1.0.0]', content)
        self.assertIn('Changelog', content)

    def test_json_files_exist_and_valid(self):
        import json
        from src.utils.i18n import get_locales_dir
        locales_dir = get_locales_dir()
        vi_json_path = os.path.join(locales_dir, 'vi.json')
        en_json_path = os.path.join(locales_dir, 'en.json')

        self.assertTrue(os.path.exists(vi_json_path), f"Missing {vi_json_path}")
        self.assertTrue(os.path.exists(en_json_path), f"Missing {en_json_path}")

        with open(vi_json_path, 'r', encoding='utf-8') as f:
            vi_data = json.load(f)
        with open(en_json_path, 'r', encoding='utf-8') as f:
            en_data = json.load(f)

        self.assertIsInstance(vi_data, dict)
        self.assertIsInstance(en_data, dict)
        self.assertGreater(len(vi_data), 50)
        self.assertEqual(len(vi_data), len(en_data))

    def test_repository_language_setting(self):
        seed_default_settings()
        set_setting('language', 'vi')
        settings = get_all_settings()
        self.assertIn('language', settings)
        self.assertEqual(settings.get('language'), 'vi')

        set_setting('language', 'en')
        updated = get_all_settings()
        self.assertEqual(updated.get('language'), 'en')

        # restore
        set_setting('language', 'vi')


if __name__ == '__main__':
    unittest.main()

