module.exports = {
    'env': {
        'browser': true,
        'es2021': true,
        'commonjs': true,
        'es6': true,
        'jquery': true
    },
    'extends': 'eslint:recommended',
    'parserOptions': {
        'ecmaVersion': 12,
        //'sourceType': 'module'
    },
    'globals': {
        'COOKIE_USERID': true,
        'go_to_video': true,
        'CMD_REFRESH': true,
        'main_ws_connect': true,
        'main_ws_reconnect': true,
        'WS_URL': true,
        'MAIN_PATH': true,
        'MAIN_PATH_S': true,
        'CMD_PING': true,
        'Playlist': true,
        'CMD_DUMP': true,
        'CMD_PLAYID': true,
        'CMD_PLAYSETT': true,
        'CMD_YT_PLAYLISTCHECK': true,
        'CMD_MEDIASET_KEYS': true,
        'find_user_cookie': true,
        'MainWSQueueElement': true,
        'PL_ADD_VIEW_TYPE_CLASS': true,
        'CMD_SEEN': true,
        'CMD_MOVE': true,
        'CMD_MEDIASET_BRANDS': true,
        'CMD_RAI_CONTENTSET': true,
        'playlist_save_prefix': true,
        'dyn_module_load': true,
        'CMD_IORDER': true,
        'CMD_DEL': true,
        'CMD_SORT': true,
        'docCookies': true,
        'CMD_RAI_LISTINGS': true,
        'bootstrapDetectBreakpoint': true,
        'COOKIE_SELECTEDPL': true,
        'COOKIE_PLAYSETT': true,
        'CMD_MEDIASET_LISTINGS': true,
        'set_next_button_enabled': true,
        'set_pause_button_enabled': true,
        'is_pause_function_active': true,
        'get_url_without_file': true,
        'set_prev_button_enabled': true,
        'set_video_title': true,
        'set_video_enabled': true,
        'get_template_name': true,
        'workout_file': true,
        'format_duration': true,
        'toast_msg': true,
        'pad': true,
        'gapi': true,
        'pako': true,
        'GOOGLE_CLIENT_ID': true,
        'URL_PARAMS': true,
        'URL_PARAMS_APPEND': true,
        'fetch': true,
        'VIDEO_STATUS_ENDED': true,
        'VIDEO_STATUS_UNSTARTED': true,
        'VIDEO_STATUS_BUFFERING': true,
        'VIDEO_STATUS_PAUSED': true,
        'VIDEO_STATUS_CUED': true,
        'VIDEO_STATUS_PLAYING': true,
        'VIDEO_STATUS_CANNOT_PLAY': true,
        'TWITCH_CLIENT_ID': true,
        'generate_rand_string': true,
        'XMLHttpRequest_get_class': true,
        'XMLHttpRequest': true,
        'dashjs': true,
        'videojs': true,
        'page_set_title': true,
        'TWITCH_VIDEO_ID_PRE': true,
        'Twitch': true,
        'on_player_load': true,
        'video_width': true,
        'video_height': true,
        'clear_playlist': true,
        'add_video_to_button': true,
        'set_playlist_button_enabled': true,
        'manage_errors': true,
        'get_startup_settings': true,
        'set_save_conf_button_enabled': true,
        'set_remove_button_enabled': true,
        'get_spinner_value': true,
        'set_spinner_value': true,
        'get_default_check': true,
        'get_remove_check': true,
        'playlist_rebuild_player': true,
        'set_remove_check': true,
        'set_default_check': true,
        'set_reset_conf_button_enabled': true,
        'add_playlist_to_button': true,
        'set_playlist_enabled': true,
        'CMD_REMOTEPLAY': true,
        'CMD_FOLDER_LIST': true,
        'CMD_REMOTEPLAY_JS': true,
        'QRCode': true,
        'main_ws_qel_exists': true,
        'CMD_REMOTEPLAY_JS_PAUSE': true,
        'CMD_REMOTEPLAY_JS_NEXT': true,
        'CMD_REMOTEPLAY_JS_DEL': true,
        'CMD_REMOTEPLAY_JS_PREV': true,
        'CMD_REMOTEPLAY_JS_FFW': true,
        'CMD_REMOTEPLAY_JS_REW': true,
        'CMD_REMOTEPLAY_JS_GOTO': true,
        'CMD_REMOTEPLAY_JS_SEC': true,
        'CMD_REMOTEPLAY_JS_TELEGRAM': true,
        'CMD_REMOTEPLAY_PUSH': true,
        'CMD_REMOTEPLAY_JS_RATE': true,
        'CMD_PLAYITSETT': true,
        'CMD_TOKEN': true,
        'get_selected_mime': true,
        'set_selected_mime': true,
        'PTHREG': true,
        'YT': true,
        'on_conf_name_change': true,
        'fill_conf_name': true,
        'set_selected_conf_name': true,
        'get_selected_conf_name': true,
        'get_conf_name': true,
        'bootstrap': true,
        'show_telegram_token': true,
        'is_telegram_token_visible': true,
        'hide_telegram_token': true,
        'set_telegram_link': true,
        'Telegram': true,
        'DOWNLOADED_SUFFIX': true,
        'globalThis': false,
        '$': true,
        'CMD_REMOTEBROWSER_JS_CLOSE': true,
        'CMD_REMOTEBROWSER_JS_ACTIVATE': true,
        'CMD_REMOTEBROWSER_JS': true,
        'CMD_REMOTEBROWSER_JS_GOTO': true,
        'CMD_REMOTEBROWSER_JS_RELOAD': true,
        'CMD_REMOTEBROWSER_JS_KEY': true,
        'browser': true,
        'chrome': true,
        'importScripts': true
    },
    'rules': {
        'indent': [
            'error',
            4
        ],
        'linebreak-style': [
            'error',
            'windows'
        ],
        'quotes': [
            'error',
            'single'
        ],
        'semi': [
            'error',
            'always'
        ],
        'no-unused-vars': ['off']
    }
};
