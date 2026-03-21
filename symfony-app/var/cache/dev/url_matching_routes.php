<?php

/**
 * This file has been auto-generated
 * by the Symfony Routing Component.
 */

return [
    false, // $matchHost
    [ // $staticRoutes
        '/api/stl/upload' => [[['_route' => 'api_stl_upload', '_controller' => 'App\\Controller\\StlUploadController::upload'], null, ['POST' => 0], null, false, false, null]],
        '/telegram/download' => [[['_route' => 'app_telegram_items', '_controller' => 'App\\Controller\\TelegramItemsController::index'], null, ['POST' => 0], null, false, false, null]],
        '/telegram-downloads/download' => [[['_route' => 'app_telegram_download_file', '_controller' => 'App\\Controller\\TelegramItemsController::downloadFile'], null, ['POST' => 0], null, false, false, null]],
    ],
    [ // $regexpList
        0 => '{^(?'
                .'|/_error/(\\d+)(?:\\.([^/]++))?(*:35)'
            .')/?$}sDu',
    ],
    [ // $dynamicRoutes
        35 => [
            [['_route' => '_preview_error', '_controller' => 'error_controller::preview', '_format' => 'html'], ['code', '_format'], null, null, false, true, null],
            [null, null, null, null, false, false, 0],
        ],
    ],
    null, // $checkCondition
];
