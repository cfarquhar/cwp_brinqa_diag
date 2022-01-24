import csv
import os
import requests
import time
import urllib3

from json.decoder import JSONDecodeError
from random import randrange
from statistics import mean

# e.g. https://us-east1.cloud.twistlock.com/us-1-123456789
CWP_API = f"{os.environ.get('CWP_CONSOLE_PATH')}/api/v1"
CWP_USER = os.environ.get("CWP_USER")
CWP_PASSWORD = os.environ.get("CWP_PASSWORD")

PAGE_SIZE = 50
RETRY_LIMIT = 10
SIMULATE_RANDOM_FAILURES = os.environ.get("SIMULATE_RANDOM_FAILURES", False)
VERIFY_TLS = not os.environ.get("TLS_INSECURE", False)


def fmt_elapsed(seconds):
    """generate a human readable duration in Hh Mm Ss format"""
    result = ""
    h = int(seconds / (60 * 60))
    m = int((seconds / 60) % 60)
    s = seconds % 60
    if h > 0:
        result += f"{h}h "
    if m > 0 or h > 0:
        result += f"{m}m "
    result += f"{s:.1f}s"
    return result


class CwpApiProfiler:
    def __init__(self, endpoint, user, password):
        self.endpoint = endpoint
        self.user = user
        self.password = password
        self.token = ""
        self.verify_tls = VERIFY_TLS
        self._details_csv = open(f"details-{int(time.time())}.csv", "w")
        self._details_csv_writer = csv.writer(self._details_csv)
        self._debug_log = open(f"debug-{int(time.time())}.log", "w")

        # Avoid cluttering output if TLS verify is False
        if not self.verify_tls:
            urllib3.disable_warnings()

        self._get_token()

        # Write csv header
        self._details_csv_writer.writerow(
            [
                "Scenario",
                "Path",
                "Parameters",
                "HTTP Response",
                "Duration (s)",
                "Result count",
            ]
        )

    def __del__(self):
        self._details_csv.close()
        self._debug_log.close()

    def _log(self, message):
        self._debug_log.write(f"{time.strftime('%c')} | {message}\n")

    def _get_token(self):
        self._log("_get_token | about to call requests.post to generate a token")
        body = {"username": self.user, "password": self.password}
        r = requests.post(
            f"{self.endpoint}/authenticate", json=body, verify=self.verify_tls
        )
        if r.status_code != 200:
            raise Exception(
                f"Unable to authenticate to {CWP_API} with provided credentials."
            )
        self.token = r.json()["token"]
        self._log("_get_token | token seems to have been issued successfully\n")

    def _get_api(self, url, headers, params):
        self._log(f"_get_api | about to call {url} with {params}")
        if SIMULATE_RANDOM_FAILURES:
            if randrange(1, 100) < 30:
                url += "fail"
        # time.sleep(120)
        start = time.perf_counter()
        r = requests.get(
            url,
            headers=headers,
            params=params,
            verify=self.verify_tls,
        )
        request_time = time.perf_counter() - start
        return (request_time, r)

    def _summarize(self, rows):
        call_timings = {}

        summary = {
            "scenario": rows[0][0],
            "api_path": f"/api/v1/{rows[0][1]}",
            "total_calls": 0,
            "total_call_duration": 0,
            "total_results": 0,
            "by_status_code": {},
        }

        for row in rows:
            status_code = row[3]
            request_duration = row[4]
            result_count = row[5]

            if status_code not in call_timings.keys():
                call_timings[status_code] = []

            call_timings[status_code].append(request_duration)
            summary["total_calls"] += 1
            summary["total_call_duration"] += request_duration
            summary["total_results"] += result_count

        for status_code in call_timings:
            summary["by_status_code"][status_code] = {
                "calls": len(call_timings[status_code]),
                "total_duration": sum(call_timings[status_code]),
                "min_duration": min(call_timings[status_code]),
                "mean_duration": mean(call_timings[status_code]),
                "max_duration": max(call_timings[status_code]),
            }

        return summary

    def _print_summary(self, summary):
        success_stats = summary["by_status_code"].get(200, {})
        success_mean_duration = success_stats.get("mean_duration", 0)
        estimate_10k = success_mean_duration * 10000 / PAGE_SIZE
        estimate_100k = success_mean_duration * 100000 / PAGE_SIZE
        estimate_120k = success_mean_duration * 120000 / PAGE_SIZE

        print("-" * (10 + len(summary["scenario"])))
        print(f"Scenario: {summary['scenario']}")
        print("-" * (10 + len(summary["scenario"])))
        print(f"API path: {summary['api_path']}")
        print(f"Total API calls made: {summary['total_calls']}")
        print(
            f"Total API response duration: {fmt_elapsed(summary['total_call_duration'])}"
        )
        print(f"Total results retrieved: {summary['total_results']}")
        if success_mean_duration > 0:
            print(
                f"Estimated time to retrieve 10k results: {fmt_elapsed(estimate_10k)}"
            )
            print(
                f"Estimated time to retrieve 100k results: {fmt_elapsed(estimate_100k)}"
            )
            print(
                f"Estimated time to retrieve 120k results: {fmt_elapsed(estimate_120k)}"
            )
        print(f"By HTTP status code:")
        for status_code in sorted(summary["by_status_code"]):
            print(f"  {status_code}:")
            print(
                f"    Total HTTP {status_code} responses: {summary['by_status_code'][status_code]['calls']}"
            )
            print(
                f"    Total response time: {fmt_elapsed(summary['by_status_code'][status_code]['total_duration'])}"
            )
            print(
                f"    Min response time: {summary['by_status_code'][status_code]['min_duration']:.3f}s"
            )
            print(
                f"    Mean response time: {summary['by_status_code'][status_code]['mean_duration']:.3f}s"
            )
            print(
                f"    Max response time: {summary['by_status_code'][status_code]['max_duration']:.3f}s"
            )
        print("\n")

    def profile(self, scenario_name, api_path, params):
        retries = 0
        finished = False
        rows = []

        params["offset"] = 0
        headers = {"Authorization": f"Bearer {self.token}"}

        self._log(
            f"profile  | starting profile for {scenario_name} / {api_path} / {params}."
        )

        while not finished and retries < RETRY_LIMIT:
            (request_time, r) = self._get_api(
                url=f"{self.endpoint}/{api_path}", headers=headers, params=params
            )

            try:
                result_count = len(r.json())
            except JSONDecodeError:
                self._log(
                    "profile  | got JSONDecodeError after call to _get_api(). setting result_count = 0."
                )
                result_count = 0

            row = [
                scenario_name,
                api_path,
                params,
                r.status_code,
                request_time,
                result_count,
            ]
            rows.append(row)
            self._details_csv_writer.writerow(row)

            if r.status_code == 401:
                self._log(
                    "profile  | got 401 response from _get_api(). calling _get_token() for a refresh."
                )
                self._get_token()
                headers = {"Authorization": f"Bearer {self.token}"}
            elif r.status_code != 200:
                self._log(
                    f"profile  | got {r.status_code} from _get_api(). incrementing retries to {retries + 1}."
                )
                time.sleep(5)
                retries += 1
            else:
                retries = 0
                if result_count < PAGE_SIZE:
                    self._log(
                        f"profile  | got 200 from _get_api().  result_count < PAGE_SIZE so we're done."
                    )
                    finished = True
                else:
                    params["offset"] += PAGE_SIZE
                    self._log(
                        f"profile  | got 200 from _get_api().  result_count >= PAGE_SIZE so setting offset to {params['offset']}."
                    )

        self._log(
            f"profile  | scenario {scenario_name} completed.  generating summary.\n"
        )
        summary = self._summarize(rows)
        self._print_summary(summary)


if __name__ == "__main__":

    # (scenario name, API path, GET parameters)
    scenarios = [
        # ("Registry image scan reports (compact)", "registry", {"compact": "true"}),
        # ("Deployed image scan reports (compact)", "images", {"compact": "true"}),
        # ("Host scan reports (full)", "hosts", {}),
        ("Registry image scan reports (full)", "registry", {}),
        ("Deployed image scan reports (full)", "images", {}),
        # ("Serverless scan reports (full)", "serverless", {}),
        # ("Code repo scan reports (full)", "coderepos", {}),
        ("Container scan reports (full)", "containers", {}),
    ]

    api = CwpApiProfiler(CWP_API, CWP_USER, CWP_PASSWORD)

    for scenario_name, api_path, params in scenarios:
        api.profile(scenario_name, api_path, params)
