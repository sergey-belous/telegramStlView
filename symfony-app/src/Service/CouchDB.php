<?php

namespace App\Service;

use GuzzleHttp\Client as CouchDBClient;

class CouchDB {
    public ?CouchDBClient $couchdb;

    public function __construct(
        public string $dbName
    ){
    }
    public function initCouchDB() {
        $this->couchdb = new CouchDBClient([
            'base_uri' => 'http://couchdb:5984/',
            'timeout'  => 2.0,
            'headers' => [
                'Accept' => 'application/json',
                'Content-Type' => 'application/json'
            ],
            'auth' => ['admin', 'password'],
        ]);
        
        // Create database if it doesn't exist
        try {
            $this->couchdb->put($this->dbName);
        } catch (\Exception $e) {
            echo 'Database exists' . PHP_EOL;
            // Database likely already exists
        }

        return $this->couchdb;
    }
}