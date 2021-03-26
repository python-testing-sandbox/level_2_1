import datetime
from unittest.mock import Mock

from PIL import UnidentifiedImageError
from freezegun import freeze_time
import pytest
from pytz import UTC

from main import (
    _set_listed_at, load_obscene_words, get_all_filepathes_recursively, get_params_from_config,
    CONFIG_SECTION_NAME, fetch_detailed_pull_requests, get_content_from_file,
    fetch_badges_urls, skip_exceptions_to_reraise, DateTimeProcessor, reorder_vocabulary, ColumnError,
    _load_workbook_from_xls)


@pytest.mark.parametrize(
    'execute_result, expected',
    [
        ([[1, 2], [3, 4]], {1, 2, 3, 4}),
        ([['word', 'word2'], ['word3', 'word4']], {'word', 'word2', 'word3', 'word4'}),
        ([['word', 'word2'], ['word2', 'word4']], {'word', 'word2', 'word4'}),
        ([], set()),
        ([[], []], set()),
    ]
)
def test_load_obscene_words(execute_result, expected, mocker):
    mock_sqlite3 = mocker.patch('main.sqlite3')
    mock_sqlite3.connect().cursor().execute().fetchall.return_value = execute_result

    assert load_obscene_words('any path') == expected


@pytest.mark.parametrize(
    'item_attrs, marketplace_slug, current_datetime, has_attr',
    [
        (['ebay_listed_at'], 'ebay', '2012-01-14 12:00:01', True),
        (['etsy_listed_at'], 'ebay', '2012-01-14 12:00:01', False),
        (['ebay_listed_at', 'etsy_listed_at'], 'ebay', '2012-01-14', True),
        ([], 'etsy', '2012-01-14 12:00:01', False),
    ]
)
def test_set_listed_at(item_attrs, marketplace_slug, current_datetime, monkeypatch, has_attr):
    with freeze_time(current_datetime):
        mock_item = Mock(spec=item_attrs)
        mock_marketplace = Mock(spec=['value'])
        mock_marketplace.value = marketplace_slug
        _set_listed_at(mock_item, mock_marketplace)

        if has_attr:
            assert getattr(mock_item, f'{mock_marketplace.value}_listed_at') == datetime.datetime.now()
        else:
            with pytest.raises(AttributeError):
                assert getattr(mock_item, f'{mock_marketplace.value}_listed_at') == datetime.datetime.now()


@pytest.mark.parametrize(
    'pathlist, is_dir, expected',
    [
        (['test.py'], False, ['test.py']),
        (['test.py', 'main.py'], False, ['test.py', 'main.py']),
        (['test.py'], True, []),
        ([], False, []),
    ]
)
def test_get_all_filepathes_recursively(mocker, pathlist, is_dir, expected):
    mocker.patch('main.Path.glob', return_value=pathlist)
    mocker.patch('main.os.path.isdir', return_value=is_dir)
    assert get_all_filepathes_recursively('any_path', 'py') == expected


@pytest.mark.parametrize(
    'params, expected, has_section',
    [
        ({'processes': '2342'}, {}, False),
        ({'processes': '2342'}, {'processes': 2342}, True),
        ({'exclude': 'any, string'}, {'exclude': ['any', ' string']}, True),
        ({'exit_zero': 'True'}, {'exit_zero': True}, True),
        ({'exit_zero': 'False'}, {'exit_zero': False}, True),
        ({'reorder_vocabulary': 'True'}, {'reorder_vocabulary': True}, True),
        ({'process_dots': 'True'}, {'process_dots': True}, True),
        ({'verbosity': '2342'}, {'verbosity': 2342}, True),
    ]
)
def test_get_params_from_config(mocker, has_section, expected, params):
    mock_parser = mocker.patch('main.configparser')
    parsed_config_file = {CONFIG_SECTION_NAME: params}
    mock_parser.ConfigParser().__getitem__.side_effect = parsed_config_file.__getitem__

    mock_parser.ConfigParser().has_section.return_value = has_section

    assert get_params_from_config('any path') == expected


@pytest.mark.parametrize(
    'open_pull_requests, expected, pull_requests_data',
    [
        ([{'number': 1}, {'number': 2}], {1: {'number': 1}}, {'number': 1}),
        ([{'number': 1}, {'number': 2}], {}, None),
    ]
)
def test_fetch_detailed_pull_requests(open_pull_requests, expected, pull_requests_data):
    mock_api = Mock(spec=['fetch_pull_request'])
    mock_api.fetch_pull_request.return_value = pull_requests_data

    assert fetch_detailed_pull_requests(mock_api, open_pull_requests) == expected


@pytest.mark.parametrize(
    'guess_encoding, content, expected, decode_error',
    [
        (True, 'Any content\nnext row', 'Any content\nnext row', False),
        (False, 'Any content', 'Any content', False),
        (False, 'Any content', None, True),
    ]
)
def test_get_content_from_file(mocker, tmpdir, guess_encoding, expected, content, decode_error):
    p = tmpdir.join('hello.txt')
    p.write(content)

    if decode_error:
        mocker_open = mocker.patch('main.open', mocker.mock_open(read_data='data'))
        mocker_open.side_effect = UnicodeDecodeError('error', b"", 0, 0, 'error')

    assert get_content_from_file(p.strpath, guess_encoding) == expected


@pytest.mark.parametrize(
    'readme_content, height, expected, has_image_error',
    [
        ('', 60, [], False),
        ('content', 60, [], False),
        ('content ![http](http://go.com)', 59, ['http://go.com'], False),
        ('content ![http](http://go.com)', 60, [], False),
        ('content ![http](http://hostname.com)', 59, ['http://hostname.com'], True),
    ]
)
def test_fetch_badges_urls(mocker, readme_content, height, expected, has_image_error):
    if has_image_error:
        mocker.patch('main.get_image_height_in_pixels', side_effect=UnidentifiedImageError)
    else:
        mocker.patch('main.get_image_height_in_pixels', return_value=height)

    assert fetch_badges_urls(readme_content) == expected


@pytest.mark.parametrize(
    'module_name, sys_modules',
    [
        ('unittest', {'unittest': Mock(spec=['SkipTest'])}),
        ('unittest2', {'unittest2': Mock(spec=['SkipTest'])}),
        ('nose', {'nose': Mock(spec=['SkipTest'])}),
        ('_pytest', {'_pytest': Mock(spec=['outcomes', 'SkipTest'])}),
    ]
)
def test_skip_exceptions_to_reraise(mocker, sys_modules, module_name):
    mock_sys = mocker.patch('main.sys')
    mock_sys.modules = sys_modules

    if module_name == '_pytest':
        sys_modules[module_name].outcomes.Skipped = sys_modules[module_name].SkipTest

    assert skip_exceptions_to_reraise() == (sys_modules[module_name].SkipTest,)


@pytest.mark.parametrize(
    'value, formats, parser, expected',
    [
        ('18 9 2018', ['%d %m %Y'], None, datetime.datetime(2018, 9, 18)),
        ('18 9 2018', [], Mock(return_value='any value'), 'any value'),
        ('18 9 2018', [], Mock(side_effect=ValueError), 'any value'),
        ('18 9 2018', ['%d $m %Y'], Mock(side_effect=ValueError), datetime.datetime(2018, 9, 18)),
    ]
)
def test_get_datetime_from_string(value, formats, parser, expected):
    processor = DateTimeProcessor(formats=formats, parser=parser)
    if parser and parser.side_effect:
        with pytest.raises(ColumnError):
            assert processor._get_datetime_from_string('18 9 2018') == expected
    else:
        assert processor._get_datetime_from_string('18 9 2018') == expected


@pytest.mark.parametrize(
    'value, expected, timezone',
    [
        ('18 9 2018', '18 9 2018', None),
        (datetime.datetime(2018, 9, 18), datetime.datetime(2018, 9, 18), None),
        (datetime.date(2018, 9, 18), datetime.datetime(2018, 9, 18), None),
        (123, None, None),
        (datetime.datetime(2018, 9, 18), datetime.datetime(2018, 9, 17, 21, tzinfo=UTC), 'UTC'),
    ]
)
def test_process_value(mocker, value, expected, timezone):
    processor = DateTimeProcessor(timezone=timezone)
    if expected:
        mocker.patch('main.DateTimeProcessor._get_datetime_from_string', return_value=expected)
        assert processor.process_value(value) == expected
    else:
        with pytest.raises(ColumnError):
            assert processor.process_value(value)


@pytest.mark.parametrize(
    'value, timezone, exception',
    [
        (123, None, ColumnError),
        (123, 'UBC', ValueError),
    ]
)
def test_process_value_with_raises(value, timezone, exception):
    with pytest.raises(exception):
        processor = DateTimeProcessor(timezone=timezone)
        assert processor.process_value(value)


@pytest.mark.parametrize(
    'content, expected',
    [
        ('\nfoo\nbar\nbaz\n', 'bar\nbaz\nfoo\n'),
        ('foo\n#bar\nbaz\n', 'foo\n\n#bar\nbaz\n'),
        ('', ''),
    ]
)
def test_reorder_vocabulary(tmpdir, content, expected):
    p = tmpdir.join('hello.txt')
    p.write(content)
    reorder_vocabulary(p.strpath)
    assert p.read() == expected


@pytest.mark.parametrize(
    'value, ctype',
    [
        (1, 2),
        (1, 3),
    ]
)
def test_load_workbook_from_xls(mocker, value, ctype):
    mock_xls_workbook = mocker.patch('main.xlrd.open_workbook', autospec=True)
    mock_xls_sheet = mock_xls_workbook().sheet_by_index()
    mock_xls_sheet.cell().value = value
    mock_xls_sheet.cell().ctype = ctype
    mock_wordbook = mocker.patch('main.Workbook')
    mocker.patch('main.datetime.datetime', return_value=value)
    mock_xls_workbook().datemode = 1

    assert _load_workbook_from_xls('any path', 'any contents') == mock_wordbook()
