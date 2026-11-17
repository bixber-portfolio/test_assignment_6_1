"""Тесты замера скорости. Запуск: python3 -m unittest -v

Сеть не нужна: тесты поднимают свой маленький HTTP-сервер на localhost.
"""
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import speedtest

PAYLOAD = b"x" * 200_000


class Handler(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):
        type(self).hits += 1
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, *args):  # без лишнего шума в консоли
        pass


class SpeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/file"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_ten_requests_and_exact_byte_count(self):
        Handler.hits = 0
        result = speedtest.measure(self.url, 10, timeout=5)
        self.assertEqual(Handler.hits, 10)
        self.assertEqual(len(result.seconds), 10)
        self.assertEqual(sum(result.sizes), 10 * len(PAYLOAD))
        self.assertEqual(result.errors, [])

    def test_summary_numbers(self):
        result = speedtest.Result(seconds=[1.0, 3.0], sizes=[1_000_000, 1_000_000])
        summary = speedtest.summarize(result)
        self.assertEqual(summary["average_seconds"], 2.0)
        self.assertEqual(summary["total_bytes"], 2_000_000)
        # 2 000 000 байт за 4 с = 500 000 байт/с = 4 Мбит/с = 0,5 МБ/с
        self.assertAlmostEqual(summary["mbit_per_second"], 4.0)
        self.assertAlmostEqual(summary["mbyte_per_second"], 0.5)

    def test_unreachable_address_is_reported_not_crashed(self):
        result = speedtest.measure("http://127.0.0.1:1/", 3, timeout=1)
        self.assertEqual(len(result.errors), 3)
        self.assertIsNone(speedtest.summarize(result)["average_seconds"])

    def test_cli_exit_codes(self):
        self.assertEqual(speedtest.main([self.url, "-n", "2"]), 0)
        self.assertEqual(speedtest.main(["http://127.0.0.1:1/", "-n", "1", "--timeout", "1"]), 1)

    def test_bad_address_is_rejected(self):
        with self.assertRaises(SystemExit):
            speedtest.main(["not-a-url"])


if __name__ == "__main__":
    unittest.main()
