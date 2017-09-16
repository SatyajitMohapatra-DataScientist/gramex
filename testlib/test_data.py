# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import io
import os
import six
import json
import unittest
import gramex.data
import gramex.cache
import pandas as pd
from orderedattrdict import AttrDict
from nose.plugins.skip import SkipTest
from nose.tools import eq_, ok_, assert_raises
from pandas.util.testing import assert_frame_equal as afe
import dbutils
from . import folder, sales_file


class TestFilter(unittest.TestCase):
    sales = gramex.cache.open(sales_file, 'xlsx')
    db = set()
    server = AttrDict(
        mysql=os.environ.get('MYSQL_SERVER', 'localhost'),
        postgres=os.environ.get('POSTGRES_SERVER', 'localhost'),
    )

    def check_filter(self, df=None, na_position='last', **kwargs):
        '''
        Tests a filter method. The filter method filters the sales dataset using
        an "args" dict as argument. This is used to test filter with frame, file
        and sqlalchemy URLs
        '''
        def eq(args, expected):
            meta = {}
            actual = gramex.data.filter(meta=meta, args=args, **kwargs)
            expected.index = actual.index
            afe(actual, expected)
            return meta

        sales = self.sales if df is None else df

        meta = eq({}, sales)
        eq_(meta['filters'], [])
        eq_(meta['ignored'], [])
        eq_(meta['sort'], [])
        eq_(meta['offset'], 0)
        eq_(meta['limit'], None)

        m = eq({'देश': ['भारत']},
               sales[sales['देश'] == 'भारत'])
        eq_(m['filters'], [('देश', '', ('भारत',))])

        m = eq({'city': ['Hyderabad', 'Coimbatore']},
               sales[sales['city'].isin(['Hyderabad', 'Coimbatore'])])
        eq_(m['filters'], [('city', '', ('Hyderabad', 'Coimbatore'))])

        m = eq({'product!': ['Biscuit', 'Crème']},
               sales[~sales['product'].isin(['Biscuit', 'Crème'])])
        eq_(m['filters'], [('product', '!', ('Biscuit', 'Crème'))])

        m = eq({'city>': ['Bangalore'], 'city<': ['Singapore']},
               sales[(sales['city'] > 'Bangalore') & (sales['city'] < 'Singapore')])
        eq_(set(m['filters']), {('city', '>', ('Bangalore',)), ('city', '<', ('Singapore',))})

        # Ignore empty columns
        m = eq({'city': ['Hyderabad', 'Coimbatore', ''], 'c1': [''], 'c2>': [''], 'city~': ['']},
               sales[sales['city'].isin(['Hyderabad', 'Coimbatore'])])

        m = eq({'city>~': ['Bangalore'], 'city<~': ['Singapore']},
               sales[(sales['city'] >= 'Bangalore') & (sales['city'] <= 'Singapore')])
        eq_(set(m['filters']), {('city', '>~', ('Bangalore',)), ('city', '<~', ('Singapore',))})

        m = eq({'city~': ['ore']},
               sales[sales['city'].str.contains('ore')])
        eq_(m['filters'], [('city', '~', ('ore',))])

        m = eq({'product': ['Biscuit'], 'city': ['Bangalore'], 'देश': ['भारत']},
               sales[(sales['product'] == 'Biscuit') & (sales['city'] == 'Bangalore') &
                     (sales['देश'] == 'भारत')])
        eq_(set(m['filters']), {('product', '', ('Biscuit',)), ('city', '', ('Bangalore',)),
                                ('देश', '', ('भारत',))})

        m = eq({'city!~': ['ore']},
               sales[~sales['city'].str.contains('ore')])
        eq_(m['filters'], [('city', '!~', ('ore',))])

        m = eq({'sales>': ['100'], 'sales<': ['1000']},
               sales[(sales['sales'] > 100) & (sales['sales'] < 1000)])
        eq_(set(m['filters']), {('sales', '>', (100,)), ('sales', '<', (1000,))})

        m = eq({'growth<': [0.5]},
               sales[sales['growth'] < 0.5])

        m = eq({'sales>': ['100'], 'sales<': ['1000'], 'growth<': ['0.5']},
               sales[(sales['sales'] > 100) & (sales['sales'] < 1000) & (sales['growth'] < 0.5)])

        m = eq({'देश': ['भारत'], '_sort': ['sales']},
               sales[sales['देश'] == 'भारत'].sort_values('sales', na_position=na_position))
        eq_(m['sort'], [('sales', True)])

        m = eq({'product<~': ['Biscuit'], '_sort': ['-देश', '-growth']},
               sales[sales['product'] == 'Biscuit'].sort_values(
                    ['देश', 'growth'], ascending=[False, False], na_position=na_position))
        eq_(m['filters'], [('product', '<~', ('Biscuit',))])
        eq_(m['sort'], [('देश', False), ('growth', False)])

        m = eq({'देश': ['भारत'], '_offset': ['4'], '_limit': ['8']},
               sales[sales['देश'] == 'भारत'].iloc[4:12])
        eq_(m['filters'], [('देश', '', ('भारत',))])
        eq_(m['offset'], 4)
        eq_(m['limit'], 8)

        cols = ['product', 'city', 'sales']
        m = eq({'देश': ['भारत'], '_c': cols},
               sales[sales['देश'] == 'भारत'][cols])
        eq_(m['filters'], [('देश', '', ('भारत',))])

        ignore_cols = ['product', 'city']
        m = eq({'देश': ['भारत'], '_c': ['-' + c for c in ignore_cols]},
               sales[sales['देश'] == 'भारत'][[c for c in sales.columns if c not in ignore_cols]])
        eq_(m['filters'], [('देश', '', ('भारत',))])

        # Non-existent column does not raise an error for any operation
        for op in ['', '~', '!', '>', '<', '<~', '>', '>~']:
            m = eq({'nonexistent' + op: ['']}, sales)
            eq_(m['ignored'], [('nonexistent' + op, [''])])
        # Non-existent sorts do not raise an error
        m = eq({'_sort': ['nonexistent', 'sales']},
               sales.sort_values('sales', na_position=na_position))
        eq_(m['ignored'], [('_sort', ['nonexistent'])])
        eq_(m['sort'], [('sales', True)])

        # Non-existent _c does not raise an error
        m = eq({'_c': ['nonexistent', 'sales']}, sales[['sales']])
        eq_(m['ignored'], [('_c', ['nonexistent'])])

        # Invalid values raise errors
        with assert_raises(ValueError):
            eq({'_limit': ['abc']}, sales)
        with assert_raises(ValueError):
            eq({'_offset': ['abc']}, sales)

    def test_frame(self):
        self.check_filter(url=self.sales)

    def test_file(self):
        self.check_filter(url=sales_file)
        afe(
            gramex.data.filter(url=sales_file, transform='2.1', sheetname='dummy'),
            gramex.cache.open(sales_file, 'excel', transform='2.2', sheetname='dummy'),
        )
        self.check_filter(
            url=sales_file,
            transform=lambda d: d[d['sales'] > 100],
            df=self.sales[self.sales['sales'] > 100],
        )
        with assert_raises(ValueError):
            gramex.data.filter(url='', engine='nonexistent')
        with assert_raises(OSError):
            gramex.data.filter(url='nonexistent')
        with assert_raises(ValueError):
            gramex.data.filter(url=os.path.join(folder, 'test_cache_module.py'))

    def check_filter_db(self, dbname, url, na_position):
        self.db.add(dbname)
        df = self.sales[self.sales['sales'] > 100]
        self.check_filter(url=url, table='sales', na_position=na_position)
        self.check_filter(url=url, table='sales', na_position=na_position,
                          transform=lambda d: d[d['sales'] > 100], df=df)
        self.check_filter(url=url, table='sales', na_position=na_position,
                          query='SELECT * FROM sales WHERE sales > 100', df=df)
        self.check_filter(url=url, table=['sales', 'sales'], na_position=na_position,
                          query='SELECT * FROM sales WHERE sales > 100',
                          transform=lambda d: d[d['growth'] < 0.5],
                          df=df[df['growth'] < 0.5])
        self.check_filter(url=url, na_position=na_position,
                          query='SELECT * FROM sales WHERE sales > 100',
                          transform=lambda d: d[d['growth'] < 0.5],
                          df=df[df['growth'] < 0.5])
        self.check_filter(url=url, table='sales', na_position=na_position,
                          query='SELECT * FROM sales WHERE sales > 100',
                          transform=lambda d: d[d['growth'] < 0.5],
                          df=df[df['growth'] < 0.5])
        afe(gramex.data.filter(url=url, table='{x}', args={'x': ['sales']}), self.sales)
        actual = gramex.data.filter(
            url=url, table='{兴}', args={'兴': ['sales'], 'col': ['growth'], 'val': [0]},
            query='SELECT * FROM {兴} WHERE {col} > {val}'
        )
        expected = self.sales[self.sales['growth'] > 0]
        expected.index = actual.index
        afe(actual, expected)

        # Test invalid parameters
        with assert_raises(ValueError):
            gramex.data.filter(url=url, table=1, query='SELECT * FROM sales WHERE sales > 100')
        with assert_raises(ValueError):
            gramex.data.filter(url=url, table={}, query='SELECT * FROM sales WHERE sales > 100')

        # Arguments with spaces raise an Exception
        with assert_raises(Exception):
            gramex.data.filter(url=url, table='{x}', args={'x': ['a b']})
        with assert_raises(Exception):
            gramex.data.filter(url=url, table='{x}', args={'x': ['sales'], 'p': ['a b']},
                               query='SELECT * FROM {x} WHERE {p} > 0')

    def test_mysql(self):
        url = dbutils.mysql_create_db(self.server.mysql, 'test_filter', sales=self.sales)
        self.check_filter_db('mysql', url, na_position='first')

    def test_postgres(self):
        url = dbutils.postgres_create_db(self.server.postgres, 'test_filter', sales=self.sales)
        self.check_filter_db('postgres', url, na_position='last')

    def test_sqlite(self):
        url = dbutils.sqlite_create_db('test_filter.db', sales=self.sales)
        self.check_filter_db('sqlite', url, na_position='first')

    @classmethod
    def tearDownClass(cls):
        if 'mysql' in cls.db:
            dbutils.mysql_drop_db(cls.server.mysql, 'test_filter')
        if 'postgres' in cls.db:
            dbutils.postgres_drop_db(cls.server.postgres, 'test_filter')
        if 'sqlite' in cls.db:
            dbutils.sqlite_drop_db('test_filter.db')


class TestDownload(unittest.TestCase):
    @classmethod
    def setupClass(cls):
        cls.sales = gramex.cache.open(sales_file, 'xlsx')
        cls.dummy = pd.DataFrame({
            'खुश': ['高兴', 'سعيد'],
            'length': [1.2, None],
        })

    def test_download_csv(self):
        out = gramex.data.download(self.dummy, format='csv')
        ok_(out.startswith(''.encode('utf-8-sig')))
        afe(pd.read_csv(io.BytesIO(out), encoding='utf-8'), self.dummy)

        out = gramex.data.download(AttrDict([
            ('dummy', self.dummy),
            ('sales', self.sales),
        ]), format='csv')
        lines = out.splitlines(True)
        eq_(lines[0], 'dummy\n'.encode('utf-8-sig'))
        actual = pd.read_csv(io.BytesIO(b''.join(lines[1:4])), encoding='utf-8')
        afe(actual, self.dummy)

        eq_(lines[5], 'sales\n'.encode('utf-8'))
        actual = pd.read_csv(io.BytesIO(b''.join(lines[6:])), encoding='utf-8')
        afe(actual, self.sales)

    def test_download_json(self):
        out = gramex.data.download(self.dummy, format='json')
        afe(pd.read_json(io.BytesIO(out)), self.dummy)

        out = gramex.data.download({'dummy': self.dummy, 'sales': self.sales}, format='json')
        result = json.loads(out, object_pairs_hook=AttrDict)

        def from_json(key):
            s = json.dumps(result[key])
            # PY2 returns str (binary). PY3 returns str (unicode). Ensure it's binary
            if isinstance(s, six.text_type):
                s = s.encode('utf-8')
            return pd.read_json(io.BytesIO(s))

        afe(from_json('dummy'), self.dummy, check_like=True)
        afe(from_json('sales'), self.sales, check_like=True)

    def test_download_excel(self):
        out = gramex.data.download(self.dummy, format='xlsx')
        afe(pd.read_excel(io.BytesIO(out)), self.dummy)

        out = gramex.data.download({'dummy': self.dummy, 'sales': self.sales}, format='xlsx')
        result = pd.read_excel(io.BytesIO(out), sheetname=None)
        afe(result['dummy'], self.dummy)
        afe(result['sales'], self.sales)

    def test_download_html(self):
        # Note: In Python 2, pd.read_html returns .columns.inferred_type=mixed
        # instead of unicde. So check column type only in PY3 not PY2
        out = gramex.data.download(self.dummy, format='html')
        result = pd.read_html(io.BytesIO(out), encoding='utf-8')[0]
        afe(result, self.dummy, check_column_type=six.PY3)

        out = gramex.data.download(AttrDict([
            ('dummy', self.dummy),
            ('sales', self.sales)
        ]), format='html')
        result = pd.read_html(io.BytesIO(out), encoding='utf-8')
        afe(result[0], self.dummy, check_column_type=six.PY3)
        afe(result[1], self.sales, check_column_type=six.PY3)

    def test_template(self):
        raise SkipTest('TODO')