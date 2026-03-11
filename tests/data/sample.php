<?php
class Logger {
    public function log($msg) {
        echo $msg;
    }
}

function init() {
    return new Logger();
}
?>
