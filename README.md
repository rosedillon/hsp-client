# hsp-client

A Python client for the Rail Delivery Group's Historic Service
Performance (HSP) API, which records how late trains between two
stations actually ran, from Darwin's historical data.

HSP is the industry's public record of past punctuality for individual
trains in Great Britain. It has no bulk download; you query it live,
and it answers with deeply nested JSON in which every number is a
string and every time that does not apply is an empty string. This
package sends the requests and turns the answers into tables.

```python
from hsp_client import HspClient, parse_service_metrics

client = HspClient()  # reads NRDP_USERNAME and NRDP_PASSWORD

raw = client.service_metrics(
    "BTN",
    "VIC",
    from_time="0700",
    to_time="0800",
    from_date="2024-01-08",
    to_date="2024-01-12",
    days="WEEKDAY",
)
frame = parse_service_metrics(raw)
```

## Install

Python 3.11 or later.

```sh
pip install git+https://github.com/rosedillon/hsp-client
```

or, from a clone, `pip install .`. It depends on pandas for the tables.
HTTP goes through `urllib` from the standard library.

## Credentials

You need a [National Rail Data Portal](https://opendata.nationalrail.co.uk)
account with HSP ticked under "Subscription type".

A missing tick is the usual reason requests fail. An NRDP account
without it works for the other feeds and gets a `401` from HSP, so the
client says what to check instead of just reporting the status code:

```
error: HSP rejected the credentials (HTTP 401). Check the username and password,
and confirm the account has 'HSP' ticked under Subscription type at
https://opendata.nationalrail.co.uk. An NRDP account without that subscription
works for the other feeds but not for HSP.
```

Set the credentials in the environment:

```sh
export NRDP_USERNAME="you@example.com"
export NRDP_PASSWORD="..."
```

The CLI has no `--password` flag and nothing here reads a password from
a config file. A flag ends up in shell history and a config file tends
to end up in git.

## The two endpoints

### `metrics`: punctuality between two stations

Every departure pattern between an origin and a destination over a
date range, with the share of services that arrived within each
tolerance.

```sh
hsp-client metrics BTN VIC \
  --from-time 0700 --to-time 0800 \
  --from-date 2024-01-08 --to-date 2024-01-12 \
  --days WEEKDAY --tolerance 5 10
```

The output has one row per departure pattern per tolerance:

```
origin_location destination_location gbtt_ptd gbtt_pta toc_code  matched_services  tolerance_value  num_tolerance  percent_tolerance
            BTN                  VIC     0722     0822       GX               9.0              5.0            8.0               88.0
            BTN                  VIC     0722     0822       GX               9.0             10.0            9.0              100.0
```

### `details`: stop-by-stop times for one service

Take a RID from the `rids` column above to see what that train did:

```sh
hsp-client details 201601013091406
```

```
location gbtt_pta actual_ta  arrival_delay gbtt_ptd actual_td  departure_delay
     BTN                              <NA>     0722      0724                2
     HHE     0739      0741              2     0740      0742                2
     VIC     0822      0819             -3                                <NA>
```

HSP does not return `arrival_delay` and `departure_delay`; they are
worked out here, in minutes late (negative if early), with `<NA>` where
the time does not apply. An origin has no public arrival and a terminus
no public departure, and HSP sends those as `""`. They are missing
values, not midnight. A train due at 23:58 that arrives at 00:03 is five
minutes late.

Add `--csv out.csv` to write a file, or `--raw` for the JSON as HSP sent
it.

## What HSP leaves out

HSP only includes a service if

- its public departure and arrival times and its operator match the
  query exactly,
- it is not marked as deleted, and
- at a location it calls at, it has a recorded actual arrival time.

The full rules are under "Rules for Inclusion of Trains" on the
[Open Rail Data wiki](https://wiki.openraildata.com/index.php/HSP). An
empty result does not mean no train ran, and the CLI says so rather
than printing nothing:

```
No services returned. HSP excludes trains whose public times or operator do not
match exactly, and those with no recorded actual arrival, so an empty result does
not prove that nothing ran.
```

Other limits:

- HSP holds roughly the last year. Older dates return nothing.
- `days` is `WEEKDAY`, `SATURDAY` or `SUNDAY`. There is no option for
  all days, so query the three and combine them.
- Up to three tolerance values per request.
- Times are `HHMM` strings and dates `YYYY-MM-DD`, both passed to HSP
  unchanged.

## Python API

| Name | |
|---|---|
| `HspClient(username=None, password=None, timeout=60)` | a connection; credentials default to the environment |
| `.service_metrics(from_loc, to_loc, ...)` | the raw `serviceMetrics` JSON |
| `.service_details(rid)` | the raw `serviceDetails` JSON |
| `parse_service_metrics(raw)` | one row per pattern per tolerance |
| `parse_service_details(raw)` | one row per calling point, with delays |
| `parse_hhmm("0712")` | minutes since midnight, or `None` |
| `delay_minutes(scheduled, actual)` | minutes late, allowing for midnight |

Every error is a subclass of `HspError`: `MissingCredentialsError`,
`AuthenticationError`, `HspRequestError` and `InvalidRequestError`. Bad
arguments raise `InvalidRequestError` before anything is sent, so a
typo in `days` costs no request.

## Development

```sh
git clone https://github.com/rosedillon/hsp-client
cd hsp-client
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check . && mypy src
```

The tests replace `urlopen` with a fake that records each request, so
they cover request building, the authentication header and error
handling with no network or credentials. The response fixtures follow
the shapes documented on the Open Rail Data wiki, string-encoded
numbers and empty-string times included.

## Licence

GPL-3.0. See [LICENSE](LICENSE).

Not affiliated with or endorsed by the Rail Delivery Group or National
Rail.
