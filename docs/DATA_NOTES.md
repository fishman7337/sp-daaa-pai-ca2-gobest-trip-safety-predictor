# Data Notes

Raw coursework data is not included in this public repository.

## Expected Input

Batch CSVs should use raw vehicle sensor records. Column names are matched case-insensitively.

Required columns:

- `booking_id` or `bookingID`
- `second`
- `speed`
- `acceleration_x`, `acceleration_y`, `acceleration_z`
- `gyro_x`, `gyro_y`, `gyro_z`
- `accuracy` or `accuracy_m`
- `bearing` or `bearing_deg`

If no booking ID is present, the app treats rows independently and generates local booking IDs.

## Cleaning Rules

- Blank, `na`, `null`, `nan`, and non-numeric batch values are coerced to missing values.
- Batch preprocessing fills missing required numeric fields with `0.0` after applying validity rules.
- Negative GPS accuracy and bearing outside `0..360` are treated as invalid.
- Real-time form input is stricter and rejects invalid values instead of silently coercing them.

## Public Repo Hygiene

Do not commit:

- Raw datasets
- Database connection strings
- SSH keys, PEM files, or passwords
- Student declaration documents
- Generated prediction exports
- Notebook outputs containing private paths or infrastructure details

The example CSV in `examples/` is synthetic and exists only to demonstrate the schema.
