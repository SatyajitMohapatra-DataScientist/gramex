from . import TestGramex
from nose.tools import ok_


class TestUI(TestGramex):
    def test_ui_sass(self):
        text = self.check('/ui/sass', headers={'Content-Type': 'text/css'}).text
        ok_('.color_arg{color:#000}' in text)
        ok_('.google_font{after:set()}')

        text = self.check('/ui/sass?color=red').text
        ok_('.color_arg{color:red}' in text)

        text = self.check('/ui/sass?font-family-base=lato').text
        ok_('.google_font{after:"{&#39;Lato&#39;}"}', 'auto-adds Google Fonts')

        text = self.check('/ui1/bootstraptheme.css?colorabc=purple').text
        ok_('--colorabc: purple' in text, '?colorabc adds --colorabc as a theme color')

    def test_ui_import(self):
        text = self.check('/ui1/theme.css', headers={'Content-Type': 'text/css'}).text
        ok_('@import "https://fonts.googleapis.com/css?family=lato"' in text, '@import: url list')
        ok_('.ui-import-a{color:red}' in text, '@import: file relative to cwd')
        ok_('.ui-import-b{color:red}' in text, '@import: file via absolute path')

        text = self.check('/ui2/theme.css', headers={'Content-Type': 'text/css'}).text
        ok_('@import "https://fonts.googleapis.com/css?family=lato"' in text, '@import: url')

    def check_vars(self, url):
        text = self.check(url).text
        ok_('--primary: red' in text, 'vars: set from YAML')
        ok_('--alpha: blue' in text, 'vars: colors from YAML')
        ok_('--empty' not in text, 'vars: empty values ignored')
        ok_('$key' not in text, 'vars: special keys ignored')

        text = self.check(url + '?primary=blue&color-alpha=').text
        ok_('--primary: blue' in text, 'vars: URL overrides YAML')
        ok_('--alpha' not in text, 'vars: URL clears YAML')
        ok_('.ui-import-a{color:blue}' in text, 'vars: cascaded into @import')

    def test_vars(self):
        self.check_vars('/ui1/theme.css')

    def test_sass2(self):
        self.check_vars('/ui/sass2')
