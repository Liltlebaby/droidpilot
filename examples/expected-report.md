# Android crash report

Source: simulated fixture for parser testing.

Crash logs and reports can contain personal data. Review and sanitize before publication.

Fatal events found: 1

## Event 1

    Thread: main
    Process: org.example.notes
    Exception: java.lang.RuntimeException: Could not open note
    Causes: java.lang.IllegalArgumentException: Missing note id
    Application frame: org.example.notes.NoteScreen.open(NoteScreen.kt:42)

Next investigation point: inspect the application source line above.
