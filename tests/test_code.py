import unittest
import pytest
import datetime
from pytz import timezone
from PIL import UnidentifiedImageError
from codes import (load_obscene_words, fetch_detailed_pull_requests, get_all_filepathes_recursively,
                   get_params_from_config, _set_listed_at, DateTimeProcessor, fetch_badges_urls,
                   skip_exceptions_to_reraise, get_content_from_file, ColumnError,
                   _load_workbook_from_xls,)
from contextlib import nullcontext


@pytest.mark.parametrize(
    'db_path, expected',
    [
        ([[1, 2, 3], [4]], {1, 2, 3, 4}),
        ([[1, 2], ['x', 'y']], {1, 2, 'x', 'y'}),
        ([], set()),
    ]
)
def test_load_obscene_words(db_path, expected, mocker):
    mock_sqlite = mocker.patch('codes.sqlite3')
    mock_sqlite.connect().cursor().execute().fetchall.return_value = db_path
    assert load_obscene_words('path') == expected


@pytest.mark.parametrize(
    'open_pull_requests, pull_request, expected',
    [
        ([{'number': 0}, {'number': 1}], {'number': 1}, {1: {'number': 1}}),
        ([{'number': 2}], None, {}),
        ([{'number': 3}], {'number': 4}, {4: {'number': 4}}),
     ]
)
def test_fetch_detailed_pull_requests(mocker, open_pull_requests, pull_request, expected):
    mock_api = mocker.Mock()
    mock_api.fetch_pull_request.return_value = pull_request
    assert fetch_detailed_pull_requests(mock_api, open_pull_requests) == expected


@pytest.mark.parametrize(
    'path_file, is_dir, extension, expected',
    [
        (['test_code.py, confest.py'], True, 'py', []),
        (['test_code.py, confest.py'], False, 'py', ['test_code.py, confest.py']),
    ]
)
def test_get_all_filepathes_recursively(path_file, is_dir, extension, expected, mocker):
    mocker.patch('codes.Path.glob', return_value=path_file)
    mocker.patch('codes.os.path.isdir', return_value=is_dir)
    assert get_all_filepathes_recursively('tests', extension) == expected


@pytest.mark.parametrize(
    'config_section, params, expected',
    [
        (False, {'processes': '0'}, {}),
        (True, {'processes': '0'}, {'processes': 0}),
        (False, {'processes': '0', 'exit_zero': 'True'}, {}),
        (True, {'reorder_vocabulary': 'True', 'exit_zero': 'True'}, {'reorder_vocabulary': True, 'exit_zero': True}),
        (True, {'verbosity': '-20', 'process_dots': 'False'}, {'process_dots': False, 'verbosity': -20}),
        (True, {'exclude': 'i,need,more, time'}, {'exclude': ['i', 'need', 'more', ' time']}),
    ]
)
def test_get_params_from_config(mocker, config_section, params, expected):
    mocker_config_parser = mocker.patch('codes.configparser', autospec=True)
    mocker_config_parser.ConfigParser().read.return_value = None
    mocker_config_parser.ConfigParser().has_section.return_value = config_section
    mocker_config_parser.ConfigParser().__getitem__.return_value = params
    assert get_params_from_config('config_path') == expected


@pytest.mark.parametrize(
    'marketplace_value, item_attr,  has_attr',
    [
        ('ebay', 'ebay_listed_at', True),
        ('etsy', 'etsy_listed_at', True),
        ('shopify', 'etsy_listed_at', False),
    ]
)
def test_set_listed_at(mocker, marketplace_value, item_attr, has_attr):
    mocker_item = mocker.Mock(spec=[item_attr])
    mocker_marketplace = mocker.Mock(spec=['value'])
    mocker_marketplace.value = marketplace_value
    mocker_datetime = mocker.patch('codes.datetime')
    mocker_datetime.datetime.now.return_value = datetime.date(2021, 9, 3)
    _set_listed_at(mocker_item, mocker_marketplace)
    if has_attr:
        print()
        assert getattr(mocker_item, f'{mocker_marketplace.value}_listed_at') == mocker_datetime.datetime.now()
    else:
        with pytest.raises(AttributeError):
            assert getattr(mocker_item, f'{marketplace_value}_listed_at') == mocker_datetime.datetime.now()


@pytest.mark.parametrize(
    'formats, side_effect, value_parser, value, expected, expectation',
    [
        (None, ValueError, None, 'value', None, pytest.raises(ColumnError)),
        (['%d %m %Y'], None, None, 'value',  datetime.datetime(2021, 3, 9, 0, 0), pytest.raises(ColumnError)),
        (None, None, '', '9 3 2021', '', nullcontext()),
    ]
)
def test_get_datetime_from_string(mocker, formats, side_effect, value_parser, value, expected, expectation):
    mocker_parser = mocker.MagicMock(side_effect=side_effect, return_value=value_parser)
    processor = DateTimeProcessor(formats=formats, parser=mocker_parser)
    with expectation:
        assert processor._get_datetime_from_string(value) == expected


@pytest.mark.parametrize(
    'user_timezone, excepted, expectation',
    [
        ('Europe/Moscow', timezone('Europe/Moscow'), nullcontext()),
        ('Australia/Broken_H', None, pytest.raises(ValueError)),
    ]
)
def test_date_time_processor(user_timezone, excepted, expectation):
    with expectation:
        processor = DateTimeProcessor(timezone=user_timezone)
        assert processor.user_timezone == excepted


@pytest.mark.parametrize(
    'format, value, expected_datetime, has_user_timezone, expected',
    [
        ('%d %m %Y', datetime.datetime(2021, 3, 9), None, False, datetime.datetime(2021, 3, 9)),
        ('%d %m %Y', datetime.date(2021, 3, 9), 'Europe/Moscow', False, datetime.datetime(2021, 3, 9, 0, 0)),
    ]
)
def test_process_value(mocker, format, value, expected_datetime, has_user_timezone, expected):
    processor = DateTimeProcessor(formats=format)
    if has_user_timezone:
        processor = DateTimeProcessor(formats=format, timezone=has_user_timezone)
    mocker.patch.object(DateTimeProcessor(), '_get_datetime_from_string', return_value=expected_datetime)
    assert processor.process_value(value) == expected


@pytest.mark.parametrize(
    'value, expected, error',
    [
        ('abx', None, ColumnError),
    ]
)
def test_process_value_error(mocker, value, expected, error):
    processor = DateTimeProcessor()
    mocker.patch('codes.DateTimeProcessor._get_datetime_from_string', side_effect=error)
    with pytest.raises(ColumnError):
        processor.process_value(value)


@pytest.mark.parametrize(
    'readme_content, image_height, error, expected',
    [
        ('![](http3:![](httpgs esefdg`)', 100, None, []),
        ('![img](http://)', 50, None, ['http://']),
        ('![img](http://)', None, None, []),
        ('![img](http://)', 100, UnidentifiedImageError(), ['http://']),
        ('', None, UnidentifiedImageError(), []),
        ('', 100, UnidentifiedImageError(), []),
    ]
)
def test_fetch_badges_urls(mocker, readme_content, image_height, error, expected):
    mocker_image_height = mocker.patch('codes.get_image_height_in_pixels', return_value=image_height)
    mocker_image_height.side_effect = error
    assert fetch_badges_urls(readme_content) == expected


@pytest.mark.parametrize(
    'sys_modules',
    [
        (['unittest']),
        (['unittest2']),
        (['nose']),
        (['_pytest']),
    ]
)
def test_skip_exceptions_to_reraise(mocker, sys_modules):
    mocker_sys = mocker.patch('codes.sys')
    mocker_test = mocker.Mock()
    mocker_test.SkipTest = unittest.SkipTest
    mocker_test.outcomes.Skipped = unittest.SkipTest
    mocker_sys.modules = {module: mocker_test for module in sys_modules}
    assert skip_exceptions_to_reraise() == (unittest.SkipTest,)


@pytest.mark.parametrize(
    'guess_encoding, data, error, expected',
    [
        (True, 'something\nelse\n', False, 'something\nelse\n'),
        (False, 'something\nelse\n', False, 'something\nelse\n'),
        (False, 'something\nelse\n', True, None),
    ]
)
def test_get_content_from_file(mocker, guess_encoding, data, error, expected):
    mocker_open_file = mocker.mock_open(read_data=data)
    mocker_read = mocker.patch('builtins.open', mocker_open_file)
    mocker.patch('codes.detect', return_value={'encoding': 'utf-8'})
    if error:
        mocker_read.side_effect = UnicodeDecodeError('error', b"any", 0, 0, 'error')
    assert get_content_from_file('text.txt', guess_encoding) == expected



@pytest.mark.parametrize(
    'value, ctype',
    [
        (1, 2),
        (1, 1),
    ]
)
def test_load_workbook_from_xls(mocker, value, ctype):
    xls_workbook_mock = mocker.patch('xlrd.open_workbook', autospec=True)
    workbook_mock = mocker.patch('codes.Workbook', return_value=mocker.MagicMock())
    xls_sheet_mock = xls_workbook_mock().sheet_by_index()
    xls_sheet_mock.cell().value = value
    xls_sheet_mock.cell().ctype = ctype
    xls_workbook_mock().datemode = 1
    mocker.patch('datetime.datetime', return_value=1)
    assert _load_workbook_from_xls('super_path', 'super_content') == workbook_mock()
