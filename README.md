# cabjovi

__*cabjovi*__ is a Raspberry Pi music player service that plays MP3
files according to a time-based schedule with GPIO-controlled mute
functionality.

The main purpose of cabjovi is to play Bon Jovi when you open the door
of a cabinet or a fridge.

**Notable features**:

- Time-based scheduling with day/hour ranges, all based on file system.
- GPIO-controlled mute via microswitch (open door means unmute).
- Random playback without immediate repeats.
- Auto-mute after a configurable inactivity timeout.

## Requirements

- Raspberry Pi with GPIO
- Python 3.11+
- [mpg123](https://www.mpg123.de/)
- Some ALSA audio interface
- Some MP3 files
- Some microswitch to know when the cabinet door opens

## Install

Through [uv](https://github.com/astral-sh/uv):

```
$ uv tool install git+https://github.com/eepp/cabjovi
```

Make sure `$HOME/.local/bin` is part of your `PATH`
environment variable.

## Usage

Create a base directory containing subdirectories named with time
range patterns.

Each subdirectory contains MP3 files to play during that time range.
cabjovi randomly selects and plays files from the matching directory.

### Directory structure

Organize your MP3 files in subdirectories named with time range
patterns:

```
DAY1-HOUR1:DAY2-HOUR
```

with:

- **`DAY1`/`DAY2`**: `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, or `sun`.
- **`HOUR1`/`HOUR2`**: `0` to `23` (24-hour format).

Example structure:

```
/home/user/music/
├─ day/
│  ├─ Bon Jovi - Livin' on a Prayer.mp3
│  ├─ Bon Jovi - You Give Love a Bad Name.mp3
│  ├─ Bon Jovi - It's My Life.mp3
│  └─ Bon Jovi - Wanted Dead or Alive.mp3
├─ night/
│  ├─ Chopin - Nocturne Op. 9 No. 2.mp3
│  ├─ Chopin - Ballade No. 1.mp3
│  └─ Chopin - Waltz in C# Minor.mp3
├─ weekend/
│  ├─ Linkin Park - In the End.mp3
│  ├─ Korn - Freak on a Leash.mp3
│  ├─ Limp Bizkit - Break Stuff.mp3
│  └─ P.O.D. - Alive.mp3
├─ mon-7:mon-22 -> day/
├─ mon-22:tue-7 -> night/
├─ tue-7:tue-22 -> day/
├─ tue-22:wed-7 -> night/
├─ wed-7:wed-22 -> day/
├─ wed-22:thu-7 -> night/
├─ thu-7:thu-22 -> day/
├─ thu-22:fri-7 -> night/
├─ fri-7:fri-22 -> day/
├─ fri-22:sat-7 -> night/
├─ sat-7:sat-22 -> weekend/
├─ sat-22:sun-7 -> night/
├─ sun-7:sun-22 -> weekend/
└─ sun-22:mon-7 -> night/
```

This plays Bon Jovi during weekday daytime (7:00 to 22:00), Chopin at
night, and nü-metal during weekend days.

As you can see, you may use symbolic links when you have redundancy.

You can add/modify/remove time range directories and MP3 files while
cabjovi is running: it selects the next MP3 file to play from the
current state of the file system after the current MP3 ends.

If no time range directory matches the current day and time, cabjovi
uses the `default` subdirectory as a fallback. If there's no `default`
subdirectory either, cabjovi doesn't play anything, checking
every 10&nbsp;seconds (configurable with `--poll-interval`) for a new
matching directory.

When time ranges overlap, cabjovi selects the narrowest (most specific)
matching range. For example, `mon-15:mon-17` wins over `mon-7:tue-16`.

### Run directly

Once installed:

```
$ cabjovi /path/to/music/directory [OPTIONS]
```

See `cabjovi --help` for command-line options: you can fine-tune
debounce times and specify GPIO/ALSA parameters.

### Run as a systemd service

1. Copy and edit the service file:

   ```
   $ cp cabjovi.example.service ~/.config/systemd/user/cabjovi.service
   ```

   Edit the `ExecStart` line with your base directory path and
   other parameters.

1. Enable and start the service:

   ```
   $ systemctl --user daemon-reload
   $ systemctl --user enable cabjovi.service
   $ systemctl --user start cabjovi
   ```

## Mute control

Connect a microswitch to short the selected GPIO pin and ground
to mute the playback.

The mute state automatically resets after 5&nbsp;minutes (configurable
with `--auto-mute-delay`) of inactivity,
in case the door remains open.
