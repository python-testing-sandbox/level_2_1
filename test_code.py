import datetime
import unittest

import pytest
from PIL import UnidentifiedImageError
from pytz import timezone

import code_2
from code_2 import (load_obscene_words, get_all_filepathes_recursively,
                    get_content_from_file, get_params_from_config,
                    fetch_badges_urls, DateTimeProcessor
                    )
from conftest import does_not_raise


@pytest.mark.parametrize(
    'db_command, expected',
    [
        ([['word', 'words'], ['word', 'words2']], {'word', 'words', 'words2'}),
        ([['word', 'words2'], ['word3', 'words2']], {'word', 'word3', 'words2'}),
        (['word', 'words'], {'s', 'o', 'r', 'w', 'd'}),
        ([[], []], set())
    ]
)
def test_load_from_obscene_words(mocker, db_command, expected):
    db_mock = mocker.patch('code_2.sqlite3')
    connection = db_mock.connect()
    cursor = connection.cursor()
    cursor.execute().fetchall.return_value = db_command

    assert load_obscene_words('path') == expected


@pytest.mark.parametrize(
    'path, isdir, expected',
    [
        (['some.py'], False, ['some.py']),
        (['some.py'], True, []),
        ([], False, []),
        ([], True, []),
        (['path/some_1.py', 'path/some_2.py'], False, ['path/some_1.py', 'path/some_2.py'])
    ]
)
def test_get_all_filepathes_recursively(mocker, path, isdir, expected):
    mocker.patch('code_2.Path.glob', return_value=path)
    mocker.patch('code_2.os.path.isdir', return_value=isdir)

    assert get_all_filepathes_recursively('path', 'py') == expected


@pytest.mark.parametrize(
    'guess_encoding, file_data, expected',
    [
        (True, 'some data', 'some data'),
        (False, 'some data', 'some data'),
    ]
)
def test_get_content_from_file_successfully(mocker, guess_encoding, file_data, expected):
    mock_open = mocker.mock_open(read_data=file_data)
    mocker.patch('code_2.detect', return_value={'encoding': 'utf-8'})
    mocker.patch('builtins.open', mock_open)

    assert get_content_from_file('some.txt', guess_encoding) == expected


def test_get_content_from_file_exception(mocker):
    mock_open = mocker.mock_open(read_data='some')
    read_file = mocker.patch('builtins.open', mock_open)
    read_file.side_effect = UnicodeDecodeError('e', b'some', 1, 0, 'e')

    assert get_content_from_file('some.txt', False) is None


@pytest.mark.parametrize(
    'param, has_section, expected',
    [
        ({'processes': '1'}, True, {'processes': 1}),
        ({'exclude': 'some,param'}, True, {'exclude': ['some', 'param']}),
        ({'exit_zero': 'True'}, True, {'exit_zero': True}),
        ({'reorder_vocabulary': 'True'}, True, {'reorder_vocabulary': True}),
        ({'process_dots': 'True'}, True, {'process_dots': True}),
        ({'verbosity': '2'}, True, {'verbosity': 2}),
        ({'verbosity': '2'}, False, {}),
    ]
)
def test_get_params_from_config(mocker, param, has_section, expected):
    mock_configparser = mocker.patch('code_2.configparser')
    mock_config = mock_configparser.ConfigParser()
    mocker.patch('code_2.dict', return_value=param)
    mock_config.has_section.return_value = has_section
    assert get_params_from_config('some_path') == expected


@pytest.mark.parametrize(
    'readme_content, pic_height, error, expected',
    [
        ('text ![picture](http://abc.jpg)', 40, None, ['http://abc.jpg']),
        ('', 40, None, []),
        ('text ![picture](http://abc.jpg)', 70, None, []),
        ('text ![picture](http://abc.svg)', 40, UnidentifiedImageError, ['http://abc.svg']),
    ],
)
def test_fetch_badges_urls(mocker, readme_content, pic_height, error, expected):
    height = mocker.patch('code_2.get_image_height_in_pixels', return_value=pic_height)
    height.side_effect = error
    assert fetch_badges_urls(readme_content) == expected


@pytest.mark.parametrize(
    'date_format, value, return_value, expected',
    [
        (['%Y-%m-%d %H:%M:%S'], '2021-07-08 12:34:25', None, datetime.datetime(2021, 7, 8, 12, 34, 25)),
        (None, '2021-07-08 13:34:25', '2021-07-08 12:34:25', '2021-07-08 12:34:25'),
    ]
)
def test_get_datetime_from_string_successfully(mocker, date_format, value, return_value, expected):
    mock_parser = mocker.MagicMock(return_value=return_value)
    daytime_obj = DateTimeProcessor(formats=date_format, parser=mock_parser)
    assert daytime_obj._get_datetime_from_string(value) == expected


@pytest.mark.parametrize(
    'date_format, wrong_value, return_value, side_effect, expected',
    [
        (['%Y-%m-%d %H:%M:%S'], '2021/07/08 13:34:25', None, None, None),
        (None, '2021/07/08 13:34:25', None, ValueError, None),
    ]
)
def test_get_datetime_from_string_error(mocker, side_effect, date_format, wrong_value, return_value, expected):
    mock_parser = mocker.MagicMock(side_effect=side_effect, return_value=return_value)
    daytime_obj = DateTimeProcessor(formats=date_format, parser=mock_parser)
    with pytest.raises(code_2.ColumnError):
        assert daytime_obj._get_datetime_from_string(wrong_value) == expected


@pytest.mark.parametrize(
    'value, time_zone, expected',
    [
        (datetime.datetime(2021, 7, 8, 12, 34, 25), None, datetime.datetime(2021, 7, 8, 12, 34, 25)),
        ('2021, 7, 8, 12, 34, 25', None, datetime.datetime(2021, 7, 8, 12, 34, 25)),
        (datetime.date(2021, 7, 8), None, datetime.datetime(2021, 7, 8, 0, 0)),
        (datetime.date(2021, 7, 8), 'Asia/Tokyo', datetime.datetime(2021, 7, 8).astimezone(timezone('Asia/Tokyo'))),
    ],
)
def test_process_value_successfully(mocker, value, time_zone, expected):
    daytime_obj = DateTimeProcessor(timezone=time_zone)
    mocker.patch('code_2.DateTimeProcessor._get_datetime_from_string', return_value=expected)
    assert daytime_obj.process_value(value) == expected


@pytest.mark.parametrize(
    'wrong_value',
    [
        ('fake date',),
        (123,),
    ],
)
def test_process_value_error(mocker, wrong_value):
    daytime_obj = DateTimeProcessor()
    mocker.patch('code_2.DateTimeProcessor._get_datetime_from_string', side_effect=code_2.ColumnError)
    with pytest.raises(code_2.ColumnError):
        daytime_obj.process_value(wrong_value)


@pytest.mark.parametrize(
    'time_zone, expectation, expected',
    [
        ('Asia/Tokyo', does_not_raise(), timezone('Asia/Tokyo')),
        ('fake', pytest.raises(ValueError), None),
    ]
)
def test_datetime_processor(time_zone, expectation, expected):
    with expectation:
        daytime_obj = DateTimeProcessor(timezone=time_zone)
        assert daytime_obj.user_timezone == expected


@pytest.mark.parametrize(
    'marketplace_value, expected',
    [
        ('ebay', 2021),
    ]
)
def test_set_listed_at(mocker, marketplace_value, expected):
    item_mock_2 = mocker.MagicMock()
    marketplace_mock = mocker.MagicMock()
    marketplace_mock.value = marketplace_value
    listed_at_field_name = f'{marketplace_value}_listed_at'
    setattr(item_mock_2, listed_at_field_name, None)

    code_2._set_listed_at(item_mock_2, marketplace_mock)

    assert getattr(item_mock_2, listed_at_field_name).year == expected


@pytest.mark.parametrize(
    'input_data, handled_data',
    [
        ('text \n \n  #\nTitle text', ['text\n', '\n', '#\n', 'Title text\n']),
        ('text', ['text\n']),
        ('', []),
        ('text \n \n  #\nTitle \n #text', ['text\n', '\n', '#\n', 'Title\n', '\n', '#text\n']),
    ],
)
def test_reorder_vocabulary(mocker, input_data, handled_data):
    mock_open = mocker.mock_open(read_data=input_data)
    mock_file = mocker.patch('builtins.open', mock_open)
    mock_file().writelines.return_value = None
    code_2.reorder_vocabulary('path/file.txt')

    mock_file().writelines.assert_called_with(handled_data)
    assert mock_file().readlines.call_count == 1


@pytest.mark.parametrize(
    'value, ctype',
    [
        (10, 3),
        (9, 2),
        (0, 3),
    ],
)
def test_load_workbook_from_xls(mocker, value, ctype):
    xls_workbook_mock = mocker.patch('xlrd.open_workbook', autospec=True)
    workbook_mock = mocker.patch('code_2.Workbook', return_value=mocker.MagicMock())
    xls_sheet_mock = xls_workbook_mock().sheet_by_index()
    xls_sheet_mock.cell().value = value
    xls_sheet_mock.cell().ctype = ctype
    xls_workbook_mock().datemode = 1
    mocker.patch('datetime.datetime', return_value=1)

    assert code_2._load_workbook_from_xls('super_path', 'super_content') == workbook_mock()


@pytest.mark.parametrize(
    'open_pull_requests, fetch_value, expected',
    [
        ([{'number': 10}], {'number': 10}, {10: {'number': 10}}),
        ([{'number': 9}], None, {}),
    ],
)
def test_fetch_detailed_pull_requests(mocker, open_pull_requests, fetch_value, expected):
    api_mock = mocker.MagicMock()
    api_mock.fetch_pull_request.return_value = fetch_value

    assert code_2.fetch_detailed_pull_requests(api_mock, open_pull_requests) == expected


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
    mocker_sys = mocker.patch('code_2.sys')
    mocker_test = mocker.Mock()
    mocker_test.SkipTest = unittest.SkipTest
    mocker_test.outcomes.Skipped = unittest.SkipTest
    mocker_sys.modules = {module: mocker_test for module in sys_modules}
    assert code_2.skip_exceptions_to_reraise() == (unittest.SkipTest,)
