<?php

/**
 * This file has been auto-generated
 * by the Symfony Routing Component.
 */

return [
    false, // $matchHost
    [ // $staticRoutes
        '/telegram/download' => [[['_route' => 'app_telegram_upload_item_to_server', '_controller' => 'App\\Controller\\TelegramItemsController::uploadItemToServer'], null, ['POST' => 0], null, false, false, null]],
        '/telegram-downloads/download' => [[['_route' => 'app_telegramitems_downloadmodelfromserver', '_controller' => 'App\\Controller\\TelegramItemsController::downloadModelFromServer'], null, ['POST' => 0], null, false, false, null]],
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
