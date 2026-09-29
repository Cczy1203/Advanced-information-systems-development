package uk.ac.uwe.ufcep603.hospital.support;

import uk.ac.uwe.ufcep603.hospital.config.AppConfig;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;

/**
 * Clock used by every worker that has to produce a date or a timestamp.
 *
 * <p>A demo needs reproducible day counts ("this letter is 9 days old"), so the date can be frozen
 * with {@code demo.clock.today} and shifted with {@code demo.clock.offset-days}. When no fixed date
 * is configured the real system date is used. Once a date is fixed, the time of day is fixed too
 * (09:00 UTC) so that "days outstanding" never changes between two runs on the same day.
 */
public final class DemoClock {

    private static final DateTimeFormatter DATE_TIME = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ssXXX");
    private static final int FIXED_HOUR = 9;

    private final LocalDate fixedToday;
    private final int offsetDays;

    public DemoClock(AppConfig config) {
        this.fixedToday = config.demoToday();
        this.offsetDays = config.demoClockOffsetDays();
    }

    /** Today's date, frozen and/or shifted when the demo configuration asks for it. */
    public LocalDate today() {
        LocalDate base = fixedToday == null ? LocalDate.now(ZoneOffset.UTC) : fixedToday;
        return base.plusDays(offsetDays);
    }

    public OffsetDateTime now() {
        if (fixedToday == null && offsetDays == 0) {
            return OffsetDateTime.now(ZoneOffset.UTC);
        }
        return today().atTime(FIXED_HOUR, 0).atOffset(ZoneOffset.UTC);
    }

    /** ISO-8601 timestamp with an offset, e.g. {@code 2025-06-16T09:00:00Z}. */
    public String timestamp() {
        return DATE_TIME.format(now());
    }

    public String date(LocalDate date) {
        return date == null ? null : date.toString();
    }

    public long daysBetween(LocalDate from, LocalDate to) {
        return ChronoUnit.DAYS.between(from, to);
    }

    public LocalDateTime localDateTime() {
        return now().toLocalDateTime();
    }
}
