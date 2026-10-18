# Simulated analysis 001: failed logins followed by a success

> Entirely synthetic exercise. No real host, user, network packet or account was monitored. The addresses below belong to ranges reserved for documentation.

## Executive summary

The `compromised` scenario, seed `2026`, generated 16 authentication events. Five failures for `admin`, coming from `203.0.113.66`, occurred between `12:30` and `12:34 UTC`. A successful login from the same IP and user was recorded at `12:35 UTC`.

The system created two alerts for the same sequence: `multiple_failed_logins` with severity `medium` and `successful_login_after_failures` with severity `high`. The second was set to `investigating` through the API, with a note identifying it as a simulation. The first remains `open`. This is a teaching decision for the lab, not a confirmation of compromise.

## Scope and reproduction

- Scenario: `compromised`
- Seed: `2026`
- Events: 16 (10 of synthetic baseline activity and 6 in the test sequence)
- Fictitious host: `auth-server-01`
- Stored run: `ac958c2bb9d5494b921fd16a81719abc`
- Correlation rule: at least 5 failures from the same IP/user within 10 minutes, followed by a success within 5 minutes

To reproduce the detections without writing to the main database:

```bash
./.venv/bin/python -m soc_lab.simulator \
	--scenario compromised --seed 2026 \
	--output /tmp/soc-lab-compromised-2026.jsonl
./.venv/bin/python -m soc_lab.cli \
	--input /tmp/soc-lab-compromised-2026.jsonl \
	--db /tmp/soc-lab-analysis.sqlite
```

## Observed evidence

| Time (UTC) | Synthetic event | Rule interpretation |
| --- | --- | --- |
| 12:30 | Failure for `admin` from `203.0.113.66` | First failure in the sequence |
| 12:31–12:33 | Three more failures from the same IP/user | The count approaches the threshold |
| 12:34 | Fifth failure from the same IP/user | The repeated-failures rule reaches 5 within 10 min |
| 12:35 | Success for `admin` from the same IP | The correlation rule raises the severity |

There are ten synthetic context events before the sequence. They do not meet the rules of the `compromised` scenario and were not used to infer a real source.

## What each field means

| Field | Value in this case | Meaning and limits |
| --- | --- | --- |
| `timestamp` | 12:30–12:35 UTC | Fictitious time of the event. UTC allows ordering sources with different time zones. |
| `event_type` | `authentication` | Classifies the record as authentication; it is not a packet capture. |
| `source_ip` | `203.0.113.66` | Synthetic source IP, reserved for documentation; it does not identify a person. |
| `username` | `admin` | Fictitious target account. The account name alone does not prove who tried to authenticate. |
| `outcome` | `failure` or `success` | Result recorded by the simulator, not confirmed by a real identity provider. |
| `hostname` | `auth-server-01` | Fictitious host that would have observed the authentication. |
| `event_id` | `evt-0011` to `evt-0016` | Sequential identifier useful for referencing each event in the set. |
| `scenario` | `compromised` | Label of the generated scenario, not a real incident classification. |

## How each rule evaluated the data

1. `multiple_failed_logins` grouped the failures by IP and counted five events in a sliding ten-minute window. This produced severity `medium`; this rule does not need to know the user.
2. `successful_login_after_failures` grouped by IP **and** user, found five failures within ten minutes and a success one minute after the last failure. Since one minute is within the five-minute correlation window, it produced severity `high`.
3. The rule does not read passwords, does not decode traffic and does not decide that an account was compromised. It compares timestamps, IP, user and outcome already present in the events.

## Why are there two alerts?

The rules answer different questions. `multiple_failed_logins` asks whether there were many failures from the same IP and produces a `medium` alert. `successful_login_after_failures` asks whether the same IP and user managed to log in right after those failures; that is why it produces `high`.

Both alerts reference the same five failure events. They do not mean two different attacks happened. In a more complete SIEM, related alerts could be grouped into a single case to reduce duplication.

## Analyst assessment

**Observation:** the event set matches exactly the conditions of both rules. The time order is consistent: failures, then success, for the same IP and user.

**Hypothesis:** if these were real logs, the sequence would justify investigating possible credential use after repeated attempts.

**What cannot be concluded:** the data was fabricated by the simulator; it does not prove that a password was discovered, that a real account was accessed or that there was malicious activity. It also does not identify a person behind the IP address.

**Possible benign explanations in a real environment:** a user mistyping the password before getting it right, authorized test automation, a shared intermediate system or support activity. The rules do not know the organizational context and can produce false positives.

## Decision and next steps

The `high` alert is marked as `investigating`; the stored note also explicitly identifies the simulation. In an authorized environment, the analyst should:

1. Confirm the address, host, authentication method and identity in the original logs of the system or identity provider.
2. Check whether the successful login and the device/session were expected.
3. Review the activity after authentication and check MFA, source and account history.
4. If real evidence confirms risk, follow the organization's procedure to revoke sessions and protect the account. Do not block automatically based on this alert alone.

## Lab state

- `multiple_failed_logins`: `open`
- `successful_login_after_failures`: `investigating`
- Automated response: none
- Impact on real systems: none
