package uk.ac.uwe.ufcep603.hospital.support;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/**
 * Deterministic reference generation.
 *
 * <p>Every reference a worker issues is a pure function of its inputs. Two consequences that matter
 * for the model:
 * <ul>
 *   <li>a retried job - the engine retries three times - produces the <em>same</em> reference, so a
 *       retry cannot create a second appointment, a second charge or a second letter;</li>
 *   <li>duplicate detection is a plain map lookup on stable keys instead of a fuzzy comparison.</li>
 * </ul>
 */
public final class Ids {

    private Ids() {
    }

    /**
     * @param prefix short uppercase tag, e.g. {@code APT}
     * @param parts  the seed values; {@code null} parts are treated as empty
     * @return e.g. {@code APT-9F31C2A0}
     */
    public static String reference(String prefix, Object... parts) {
        StringBuilder seed = new StringBuilder();
        for (Object part : parts) {
            seed.append(part == null ? "" : String.valueOf(part)).append('|');
        }
        return prefix + "-" + digest(seed.toString());
    }

    /** Stable key for map lookups; never shown to a user. */
    public static String key(Object... parts) {
        StringBuilder seed = new StringBuilder();
        for (Object part : parts) {
            seed.append(part == null ? "" : String.valueOf(part)).append('\u0001');
        }
        return digest(seed.toString());
    }

    private static String digest(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().withUpperCase().formatHex(hash, 0, 4);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is not available in this JVM", e);
        }
    }
}
