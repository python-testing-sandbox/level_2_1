import unittest
from PIL import UnidentifiedImageError
import datetime
from unittest import mock
from pytz import timezone
import pytest
from contextlib import nullcontext as does_not_raise

import filecode
from level1_basics.code import ColumnError


@pytest.mark.parametrize(
    'fetchall, expected',
    [
        ([[1, 2], [3, 4], [5]], {1, 2, 3, 4, 5}),
        ([['a', 'b', 'c'], ['d']], {'a', 'b', 'c', 'd'}),
        ([[1, 2], ['a', 'b']], {1, 2, 'a', 'b'}),
        ([], set()),
        ([[], []], set()),
    ]
)
def test_load_obscene_words(mocker, fetchall, expected):
    mock_sqlite = mocker.patch('filecode.sqlite3')
    mock_sqlite.connect().cursor().execute().fetchall.return_value = fetchall
    assert filecode.load_obscene_words('path') == expected


@pytest.mark.parametrize(
    'isdir, expected',
    [
        (True, []),
        (False, ['images/image.jpg', 'pictures/picture.jpg']),
    ]
)
def test_get_all_filepathes_recursively(mocker, isdir, expected):
    mock_path = mocker.patch('filecode.Path')
    mock_os = mocker.patch('filecode.os.path')
    mock_path().glob.return_value = ['images/image.jpg', 'pictures/picture.jpg']
    mock_os.isdir.return_value = isdir
    assert filecode.get_all_filepathes_recursively('path', 'extension') == expected


@pytest.mark.parametrize(
    'guess_encoding, expected',
    [
        (True, b'data\n'),
        (False, b'data\n'),
        (False, None),
    ]
)
def test_get_content_from_file(mocker, guess_encoding, expected):
    mock_fileopen = mocker.patch('filecode.open', mocker.mock_open(read_data=b'data\n'))
    if expected is None:
        mock_fileopen.side_effect = UnicodeDecodeError('error', b"", 0, 0, 'error')
    assert filecode.get_content_from_file('filepath', guess_encoding) == expected
    if guess_encoding:
        mock_fileopen.assert_called_with('filepath', 'r', encoding='ascii')


@pytest.mark.parametrize(
    'has_section, params, expected',
    [
        (False, {}, {}),
        (True, {'processes': '1', 'exclude': 'value,value'}, {'processes': 1, 'exclude': ['value', 'value']}),
        (True, {'exit_zero': 'True', 'reorder_vocabulary': 'False'}, {'exit_zero': True, 'reorder_vocabulary': False}),
        (True, {'exit_zero': 'False', 'reorder_vocabulary': 'True'}, {'exit_zero': False, 'reorder_vocabulary': True}),
        (True, {'process_dots': 'True', 'verbosity': '1'}, {'process_dots': True, 'verbosity': 1}),
        (True, {'process_dots': 'False'}, {'process_dots': False}),
    ]
)
def test_get_params_from_config(mocker, has_section, params, expected):
    mock_parser = mocker.patch('filecode.configparser.ConfigParser', autospec=True)
    mock_parser.return_value = mocker.MagicMock()
    mock_parser.read.return_value = None
    mock_parser().has_section.return_value = has_section
    mock_parser().__getitem__.return_value = params
    assert filecode.get_params_from_config('config_path') == expected


@pytest.mark.parametrize(
    'readlines_value, called_with, expected',
    [
        (
            ['The first line.\n', '#\n', ' ', 'The last line.\n'],
            ['The first line.\n', '\n', '#\n', 'The last line.\n'],
            None,
        ),
        (
            ['The first line.\n', '\n', ' ', 'The last line.\n'],
            ['The first line.\n', 'The last line.\n'],
            None,
        ),
    ]
)
def test_reorder_vocabulary(mocker, readlines_value, called_with, expected):
    mock_open = mock.mock_open(read_data='data')
    mock_open.return_value.__iter__ = lambda self: self
    mock_open.return_value.__next__ = lambda self: self.readline()
    mock_fileopen = mocker.patch('filecode.open', mock_open, create=True)
    mock_fileopen().readlines.return_value = readlines_value
    mock_fileopen().writelines.return_value = None
    assert filecode.reorder_vocabulary('path') == expected
    mock_fileopen().writelines.assert_called_with(called_with)
    assert mock_fileopen().readlines.call_count == 1


@pytest.mark.parametrize(
    'open_pull_requests, pr, expected',
    [
        ([{'number': 3}, {'number': 4}], {'number': 'number'}, {'number': {'number': 'number'}}),
        ([{'number': 3}, {'number': 4}], None, {}),
    ]
)
def test_fetch_detailed_pull_requests(mocker, open_pull_requests, pr, expected):
    mock_api = mocker.Mock()
    mock_api.fetch_pull_request.return_value = pr
    assert filecode.fetch_detailed_pull_requests(mock_api, open_pull_requests) == expected


@pytest.mark.parametrize(
    'timezone, expected_user_timezone, expectation',
    [
        ('US/Eastern', timezone('US/Eastern'), does_not_raise()),
        ('US/Western', None, pytest.raises(ValueError)),
    ]
)
def test_date_time_processor(timezone, expected_user_timezone, expectation):
    with expectation:
        processor = filecode.DateTimeProcessor(timezone=timezone)
        assert processor.user_timezone == expected_user_timezone


@pytest.mark.parametrize(
    'value, get_datetime, has_user_timezone, expected',
    [
        ('25 3 2021', datetime.datetime(2021, 3, 25), False, datetime.datetime(2021, 3, 25)),
        (datetime.datetime(2021, 3, 25), None, False, datetime.datetime(2021, 3, 25)),
        (datetime.date(2021, 3, 25), None, False, datetime.datetime(2021, 3, 25, 0, 0)),
        (datetime.datetime(2021, 3, 25), None, True, datetime.datetime(2021, 3, 25).astimezone(timezone('US/Eastern'))),
    ]
)
def test_process_value(mocker, value, get_datetime, has_user_timezone, expected):
    processor = filecode.DateTimeProcessor(formats=['%d %m %Y'])
    if has_user_timezone:
        processor = filecode.DateTimeProcessor(formats=['%d %m %Y'], timezone='US/Eastern')
    mocker.patch.object(filecode.DateTimeProcessor(), '_get_datetime_from_string', return_value=get_datetime)
    assert processor.process_value(value) == expected


@pytest.mark.parametrize(
    'value, expected, expectation',
    [
        (123, None, pytest.raises(ColumnError)),
    ]
)
def test_process_value_with_exception(value, expected, expectation):
    processor = filecode.DateTimeProcessor()
    with expectation:
        assert processor.process_value(value) == expected


@pytest.mark.parametrize(
    'formats, parser_side_effect, value, expected, expectation',
    [
        (None, ValueError, 'value', None, pytest.raises(ColumnError)),
        (None, 'value', 'value', 'value', does_not_raise()),
        (['%d %m %Y'], None, 'value', None, pytest.raises(ColumnError)),
        (['%d %m %Y'], None, '25 3 2021', datetime.datetime(2021, 3, 25), does_not_raise())
    ]
)
def test_get_datetime_from_string(mocker, formats, parser_side_effect, value, expected, expectation):
    mock_parser = mocker.MagicMock(side_effect=parser_side_effect)
    processor = filecode.DateTimeProcessor(formats=formats, parser=mock_parser)
    with expectation:
        processor._get_datetime_from_string(value) == expected


@pytest.mark.parametrize(
    'marketplace_value, has_attr',
    [
        ('ebay', True),
        ('etsy', False),
    ]
)
def test_set_listed_at(mocker, marketplace_value, has_attr):
    mock_marketplace, mock_item = mocker.Mock(), mocker.Mock()
    mock_datetime, mock_setattr = mocker.patch('filecode.datetime'), mocker.patch('filecode.setattr')
    mock_hasattr = mocker.patch('filecode.hasattr', return_value=has_attr)
    mock_datetime.datetime.now.return_value = datetime.date(2021, 1, 1)
    mock_marketplace.value = marketplace_value
    filecode._set_listed_at(mock_item, mock_marketplace)

    mock_hasattr.assert_called_with(mock_item, f'{marketplace_value}_listed_at')
    if has_attr:
        mock_setattr.assert_called_with(mock_item, f'{marketplace_value}_listed_at', mock_datetime.datetime.now())


@pytest.mark.parametrize(
    'image_height, side_effect, readme_content, expected',
    [
        (None, None, '', []),
        (None, None, '![](httpG+D!d[.l)', []),
        (10, None, '![](httpG+D!d[.l) ![](httpg ?d[+g`)', ['httpG+D!d[.l', 'httpg ?d[+g`']),
        (10, UnidentifiedImageError(), '![](httpG+D!d[.l)', ['httpG+D!d[.l']),
        (60, None, '![](httpG+D!d[.l)', [])
    ]
)
def test_fetch_badges_url(mocker, image_height, side_effect, readme_content, expected):
    mock_image_height = mocker.patch('filecode.get_image_height_in_pixels', return_value=image_height)
    mock_image_height.side_effect = side_effect
    assert filecode.fetch_badges_urls(readme_content) == expected


@pytest.mark.parametrize(
    'cell_value, ctype_value, call_datetime',
    [
        (1, 3, True),
        (1, 1, False),
        (0, 3, False)
    ]
)
def test_load_workbook_from_xls(mocker, cell_value, ctype_value, call_datetime):
    mock_xlrd = mocker.patch('filecode.xlrd', autospec=True)
    mock_wordbook = mocker.patch('filecode.Workbook', return_value=mocker.MagicMock())
    xls_sheet = mock_xlrd.open_workbook().sheet_by_index()
    xls_sheet.cell().value = cell_value
    xls_sheet.cell().ctype = ctype_value
    mock_datetime = mocker.patch('filecode.datetime.datetime')
    assert filecode._load_workbook_from_xls('file_path', 'filecontents') == mock_wordbook()
    assert mock_xlrd.open_workbook().sheet_by_index().cell.call_count == 3
    mock_wordbook()[mock_wordbook.sheetnames()].cell.assert_called_with(row=1, column=1)
    if call_datetime:
        assert mock_datetime.call_count == 1


@pytest.mark.parametrize(
    'modules',
    [
        (['unittest']),
        (['unittest2']),
        (['nose']),
        (['_pytest']),
        (['unittest', 'unittest2', 'nose', '_pytest'])
    ]
)
def test_skip_exceptions_to_reraise(mocker, modules):
    mock_sys = mocker.patch('filecode.sys')
    mock_test = mocker.Mock()
    skip_test = unittest.SkipTest
    mock_test.SkipTest = skip_test
    mock_test.outcomes.Skipped = skip_test
    mock_sys.modules = {module: mock_test for module in modules}
    assert filecode.skip_exceptions_to_reraise() == (unittest.SkipTest,)
