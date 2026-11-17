#!/usr/bin/env python3
"""Замер скорости скачивания: N последовательных запросов к одному адресу."""
import argparse
import sys
import time
import urllib.request
from dataclasses import dataclass, field

CHUNK_SIZE = 64 * 1024  # читаем ответ кусками по 64 КиБ, чтобы не держать файл в памяти


@dataclass
class Result:
    seconds: list = field(default_factory=list)  # время каждого успешного запроса
    sizes: list = field(default_factory=list)    # размер ответа в байтах для каждого успешного
    errors: list = field(default_factory=list)   # тексты ошибок неудачных запросов


def fetch(url, timeout):
    """Один запрос: скачивает ответ целиком. Возвращает (секунды, байты)."""
    request = urllib.request.Request(url, headers={
        "User-Agent": "speedtest-script/1.0",
        "Accept-Encoding": "identity",  # без сжатия, чтобы считать реальный объём
        "Cache-Control": "no-cache",
    })
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        size = 0
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
    return time.perf_counter() - start, size


def measure(url, count, timeout, fetcher=fetch, on_request=None, on_start=None):
    """Делает count запросов подряд (следующий начинается после полного ответа на предыдущий)."""
    result = Result()
    for number in range(1, count + 1):
        if on_start:
            on_start(number)
        try:
            seconds, size = fetcher(url, timeout)
        except Exception as error:  # сеть, таймаут, HTTP-ошибка: запоминаем и идём дальше
            result.errors.append(f"запрос {number}: {error}")
            if on_request:
                on_request(number, None, None, error)
            continue
        result.seconds.append(seconds)
        result.sizes.append(size)
        if on_request:
            on_request(number, seconds, size, None)
    return result


def summarize(result):
    """Считает итоги. Скорость = весь объём / всё время (а не среднее из скоростей запросов)."""
    total_bytes = sum(result.sizes)
    total_seconds = sum(result.seconds)
    ok = len(result.seconds)
    average = total_seconds / ok if ok else None
    bytes_per_second = total_bytes / total_seconds if total_seconds > 0 else None
    return {
        "ok": ok,
        "average_seconds": average,
        "total_bytes": total_bytes,
        "mbit_per_second": bytes_per_second * 8 / 1_000_000 if bytes_per_second else None,
        "mbyte_per_second": bytes_per_second / 1_000_000 if bytes_per_second else None,
    }


def http_url(value):
    if not value.startswith(("http://", "https://")):
        raise argparse.ArgumentTypeError("адрес должен начинаться с http:// или https://")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="Замер скорости скачивания по N запросам подряд.")
    parser.add_argument("url", type=http_url, help="адрес, к которому стучаться (например, большая картинка)")
    parser.add_argument("-n", "--count", type=int, default=10, help="число запросов (по умолчанию 10)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="таймаут ожидания данных от сервера, секунд (по умолчанию 30)")
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("число запросов должно быть не меньше 1")

    def start(number):
        # печатаем сразу, до ответа сервера: иначе при долгом ожидании кажется, что скрипт завис
        print(f"Запрос {number}: ", end="", flush=True)

    def show(number, seconds, size, error):
        if error is None:
            print(f"{seconds:.3f} с, {size / 1_000_000:.2f} МБ", flush=True)
        else:
            print(f"ошибка ({error})", flush=True)

    print(f"Адрес: {args.url}", flush=True)
    result = measure(args.url, args.count, args.timeout, on_request=show, on_start=start)
    summary = summarize(result)

    print()
    print(f"Успешных запросов: {summary['ok']} из {args.count}")
    if summary["ok"] == 0:
        print("Скорость посчитать нельзя: ни один запрос не удался.", file=sys.stderr)
        return 1
    print(f"Среднее время запроса: {summary['average_seconds']:.3f} с")
    print(f"Всего скачано: {summary['total_bytes'] / 1_000_000:.2f} МБ ({summary['total_bytes']} байт)")
    if summary["mbit_per_second"] is None:
        print("Скорость скачивания: не определена (нулевое время или пустой ответ)")
    else:
        print(f"Скорость скачивания: {summary['mbit_per_second']:.2f} Мбит/с "
              f"({summary['mbyte_per_second']:.2f} МБ/с)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
