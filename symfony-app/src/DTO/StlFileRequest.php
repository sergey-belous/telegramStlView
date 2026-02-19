<?php

namespace App\DTO;

use ArrayAccess;
use Symfony\Component\Serializer\Annotation\Groups;

class StlFileRequest /*implements ArrayAccess*/ {
    public function __construct(
        #[Groups(groups:['StlFileRequest.all'])]
        public string $filePath
    )
    {
    }

    // ArrayAccess interface methods
    // public function offsetExists($offset): bool
    // {
    //     return isset($this->media[$offset]);
    // }

    // public function offsetGet($offset): mixed
    // {
    //     return $this->media[$offset] ?? null;
    // }

    // public function offsetSet($offset, $value): void
    // {
    //     if (is_null($offset)) {
    //         $this->media[] = $value;
    //     } else {
    //         $this->media[$offset] = $value;
    //     }
    // }

    // public function offsetUnset($offset): void
    // {
    //     unset($this->media[$offset]);
    // }
}