# Contributing

Report bugs with the RV version, Windows version, reproduction steps and the relevant error message. Remove account details, tokens and private connection data from logs.

For code changes:

1. Create a branch and edit the source files.
2. Run the relevant [development checks](docs/DEVELOPMENT.md).
3. For installer or updater changes, cover failures such as corrupted archives, offline operation, downgrade attempts and preservation of user settings.
4. Describe the resulting behaviour and validation in your pull request.

Keep player saves, tokens, accounts, personal Steam peers, logs and large binary archives out of Git. Binary builds belong in Releases; versions and checksums must match their contents. Keep public documentation in English and preserve both supported interface languages.
