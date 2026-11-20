Read this part at each turn before the Rule and the day's marks are read, when a bell rings, when the principal says what became of an office item or sets an office aside, before an item run by the session is run, and at a sync of the calendar.

**`ordo/rule`**, the principal's. An invented example:

```json
{
  "day_start": "05:00",
  "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
  "bells": [
    {"time": "08:00", "name": "Morning",
     "office": ["Water the plants", {"label": "Feed the goldfish", "ask": true},
                {"label": "Copy out the seed list", "by": "session"}]},
    {"time": "21:00", "time_by_day": {"sat": "22:30"}, "name": "Evening",
     "office": [{"label": "Put out the recycling", "days": ["thu"]},
                {"label": "Cover the seedlings", "off_from": "11-01", "off_to": "02-28"},
                {"label": "Wind the clock", "except_days": ["sat"]}]}
  ]
}
```

- `day_start`, `HH:MM`, `00:00` where missing: the Rule's day begins then. Before it, the day
  is the calendar day before, for the bells, every weekday filter, the off ranges and the
  marks' date; a bell whose time is before `day_start` rings after midnight, at the end of the
  Rule's day.
- `days`: the weekdays the Rule rings on, each a name in any case read by its first three
  letters or a number from 0 to 6, Sunday 0; every day where missing or empty.
- `bells`, each with `time`, `HH:MM`, two digits each, on a 24-hour clock in the viewer's
  local time, without
  which the bell is ignored, and which names it in the marks' keys; `time_by_day`, a weekday to
  `HH:MM`, moving the bell that day and not its keys; `name`; and `office`, a list of items, each
  a label or an object with `label`, without which it is dropped, `days` and `except_days`,
  weekdays it rings on or not, `off_from` and `off_to`, `MM-DD`, both needed, an inclusive
  range of the year
  it is off, wrapping the new year where `off_from` is the later, and `ask`, `true` where the
  page cannot tell whether the item is due, so that the speaker asks, the question put on the page
  as an action (rule 10), and may mark it not due;
  and `by`, `"session"` where the item is the session's to run and not the principal's to
  report, any other value ignored. Such an item is never the principal's next action: it is
  left out of the notice, its counts, the card and "Then:", and shown only in the context
  panel, marked as run by the session with its state. The speaker itself runs
  it, with its own tools, when the timing is right, puts any question it raises on the page as an
  action (rule 10), and writes its mark, `taken` when it starts and the bare time when it is done;
  the principal never reports it.
  An item filtered out for the day is neither shown nor counted.
- The page finds the latest bell rung on the Rule's day. While that bell has an item of the
  principal's open or taken, the notice stands, saying the office is not yet taken up, is under
  way, or how many items are left, with the next bell under it; the next action is the first
  such item taken, else the first open one, "Under way since" the time it was taken where it
  was, the others after "Then:", those resolved listed as done, overruled or not due, a line
  asking the principal to tell the session when it is done, and the speaker's own `next` in a
  quiet "After the office" block, with its deferred action under it where one is set. While
  `office_deferred` names that bell and was set after it rang today, `next` shows instead, with
  the office under it as set aside.
  The pending action is not replaced by the office when the bell rings. While `next` has a
  `put_at` before the moment the latest bell rang on the current Rule day and is not `asks:
  false`, every bell rung that Rule day after `put_at` is carried: their items of the principal's,
  the earliest bell's first, are the office, and a second bell during the hold neither ends it
  nor drops the first bell's items. While, too, it has no `resolved_at` at or after its
  `put_at`, the carried office has an item of the principal's open and none taken, the card
  shows `next` exactly as when no office is unresolved, and under its prompt a quiet block,
  "After this: the <bell name> office" ("the Morning and Evening offices" where two are carried),
  lists the items left, with the time each bell rang; the notice stands, saying the latest bell
  has rung and that its office, or the offices named, follow this action. Once `next` is resolved
  by `resolved_at`, the very next thing the card shows is the carried office's first item, as
  above, then the rest in order. A `next` put at or after the latest bell rang, or with no
  `put_at` or one that does not parse, carries nothing and never holds the card while that
  bell's office has an item of the principal's unresolved; nor does an action with `asks:
  false`, of any kind; nor does any `next` while an item of the carried office is under way:
  once that item is done, overruled or not due, the hold resumes while the action is still
  pending, the action first again and the items left after it. While the carry is in force, the
  notice counts the carried offices' items and names those offices where they are not the latest
  bell's alone, and the panel lists every carried bell with its items.
  `office_deferred`, where it holds, comes before all of this. The hold is bounded by nothing but
  its resolving: a `next` left pending from an earlier Rule day holds every bell of the next day
  until the principal resolves it; whether a hold lapses when no sitting is open is an open line
  for the user.
  Once every item of the principal's is resolved the notice goes and `next` shows, even while
  items run by the session remain. An earlier bell's unresolved items are not shown, save those a
  pending action carries. It reads the clock again every thirty seconds.

**`ordo/ticks-<day>`**, the marks: `<day>` the Rule's day as `YYYY-MM-DD`, the local date moved
back a day before `day_start`. It is a flat map from an office item's key to a value. The key is
`bell-<HHMM>-<slug>`, the bell's base `time` without its colon and the item's label as a slug:
the label in lower case, every run of characters but `a-z` and `0-9` made one `-`, trimmed of `-`
and cut to sixty characters, `item` where nothing is left; a label repeated in one bell's office
takes `-2`, `-3` and so on, counted over the whole list with the items filtered out, so that a
key does not shift from day to day. A label changed is a key changed. A value is `null`, or no
key, open; `taken <ISO time>`, under way since then and still unresolved; an ISO time alone,
done, any other value being read as open; `overruled <ISO time>`, overruled; and `notdue <ISO
time>`, not due today. An item is
unresolved while open or taken. The day's first mark is a `set` of the whole document, which
does not yet exist; each later one an `update` of its key. A measured value the principal
reports with an item, a weight for example, is kept as a plain field of the same document
beside the marks, under a key that does not begin with `bell-`; the page reads only the items'
keys and passes it by. An invented example:

```json
{"bell-0800-water-the-plants": "2030-01-02T08:10:00.000Z",
 "water_used": "2 l",
 "bell-2100-wind-the-clock": "overruled 2030-01-02T21:05:00.000Z",
 "bell-2100-cover-the-seedlings": "taken 2030-01-02T21:12:00.000Z"}
```

**`ordo/agenda`**, the principal's calendar for the panel, written whole by the speaker at each
sync after reading the principal's calendar, with the events of at least the next forty-eight
hours. It is the principal's private data like `ordo/rule`. An invented example:

```json
{"events": [{"start": "2030-01-02T14:00:00Z", "end": "2030-01-02T15:00:00Z",
             "title": "An example visit"},
            {"start": "2030-01-03", "end": "2030-01-04", "title": "An example fair",
             "all_day": true}],
 "fetched": "2030-01-02T09:12:00Z"}
```

- `events`, each with `start` and `end`, ISO times with an offset, or for an `all_day` event a
  bare date read as local midnight, `end` exclusive; `title`, shown as written; and `all_day`,
  `true` for an event shown as "All day". An event without a valid `start` or a `title` is
  dropped, and a missing `end` counts as the start.
- `fetched`, when the calendar was read, shown as the panel's last line.

At each turn the speaker reads and writes (rule 7): the Rule's day from the local clock, then
`ordo/rule` and `ordo/ticks-<that day>` by `get`; the bells rung so far, each at its time for
that weekday; their items that apply that day, and each item's state from its key. While the
latest bell has an item of the principal's unresolved, the page is putting the office and not
`next`, an item taken before any open one, until each of the principal's is done, overruled or
not due, or the principal sets the office aside, except while an action put before the bell rang
is still pending: then the page is putting that action, the office after it, and the pending
action is resolved after the bell, then the very next item is the office item; items run by the session never hold the card. When the
principal says in the session that an item is under way, done, not now, not due, or open again,
the speaker reads the clock and writes `taken`, the bare time, `overruled`, `notdue` or `null`.
An item overruled or marked not due is the principal's word for the day, and is not put again.
An earlier bell's unresolved items, set aside or not, the page does not show on the card, save
those a pending action carries: the
speaker lists each in the action context as still due from that bell until the principal says
done, overruled or not due for it, and lets none lapse without that word. Items with `by:
"session"` the speaker runs itself, with its own tools, when the timing is right, and marks. When
the principal sets the office aside, the speaker writes `office_deferred`, only at the principal's
word; when the principal takes it up again, the speaker removes it, and it removes it too in its
first write after a later bell has rung or the Rule's day has turned. Whenever the speaker
puts a new action as `next` it reads the clock and stamps `next.put_at` in the same write, and
never stamps it anew on a rewrite of the same action; when the principal says the pending
action is resolved, the speaker writes `next.resolved_at`, and replaces `next` only once the
office it carried is resolved, since a new `next` carries no bell rung before it; the office
item is then the next thing put; the speaker never puts the office in place of a pending action
on its own. So the office waits behind an action put before the bell rang and still pending,
and is resolved after it. At each sync the speaker
reads the principal's calendar and `set`s `ordo/agenda` whole, with `fetched`.
