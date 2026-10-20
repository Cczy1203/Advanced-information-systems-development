package uk.ac.uwe.ufcep603.hospital;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * A {@code JobClient} that records what it was asked to do, and does nothing.
 *
 * <p>{@link AbstractHospitalWorker#handle} ends in exactly one of three calls -
 * complete the job, throw a BPMN error, or fail the job so the engine retries it -
 * and which one it picks is the whole of the worker layer's error handling. That
 * choice was untested, because {@code JobClient} is a fluent builder with a wide
 * interface and the project has no mocking library.
 *
 * <p>Rather than stub the builders, this proxies whatever interface each call
 * returns: {@code newCompleteCommand(long)} returns one interface, {@code send()}
 * the next, and the method's own return type is the interface to hand back. Only
 * {@code join()} terminates a chain, and that is where the call is recorded.
 */
final class RecordingJobClient {

    enum Kind { COMPLETE, THROW_ERROR, FAIL }

    record Call(Kind kind, long jobKey, Map<String, Object> arguments) {
        Object argument(String name) { return arguments.get(name); }
    }

    private final List<Call> calls = new ArrayList<>();

    List<Call> calls() { return List.copyOf(calls); }

    /** The single command the worker issued; fails loudly if it issued none or several. */
    Call only() {
        if (calls.size() != 1) {
            throw new AssertionError("expected exactly one job command, got " + calls);
        }
        return calls.get(0);
    }

    Object client() {
        // JobClient itself is the entry point; its methods return the builder interfaces.
        return Proxy.newProxyInstance(
                RecordingJobClient.class.getClassLoader(),
                new Class<?>[]{io.camunda.zeebe.client.api.worker.JobClient.class},
                (proxy, method, args) -> handle(null, method, args));
    }

    private Object handle(State state, Method method, Object[] args) {
        String name = method.getName();
        Class<?> returnType = method.getReturnType();

        // join() is the end of a chain: the call is finished, so record it
        if ("join".equals(name) || "get".equals(name)) {
            if (state != null) {
                calls.add(state.toCall());
            }
            return primitiveDefault(returnType);
        }

        // a new command starts a fresh chain, keyed on the job it applies to
        if (state == null && name.startsWith("new") && args != null && args.length == 1
                && args[0] instanceof Long key) {
            state = new State(kindFor(name), key);
        }

        // everything else is a setter on the chain: remember what it was told
        if (state != null && args != null && args.length >= 1) {
            state.arguments.put(name, args[0]);
        }

        if (returnType.isInterface()) {
            State carried = state;
            return Proxy.newProxyInstance(
                    RecordingJobClient.class.getClassLoader(),
                    new Class<?>[]{returnType},
                    (proxy, next, nextArgs) -> handle(carried, next, nextArgs));
        }
        return primitiveDefault(returnType);
    }

    private static Kind kindFor(String starter) {
        return switch (starter) {
            case "newCompleteCommand" -> Kind.COMPLETE;
            case "newThrowErrorCommand" -> Kind.THROW_ERROR;
            case "newFailCommand" -> Kind.FAIL;
            default -> throw new UnsupportedOperationException(
                    "the worker issued a command this double does not model: " + starter);
        };
    }

    private static Object primitiveDefault(Class<?> type) {
        if (!type.isPrimitive()) return null;
        if (type == boolean.class) return false;
        if (type == void.class) return null;
        if (type == char.class) return (char) 0;
        if (type == long.class) return 0L;
        if (type == double.class) return 0d;
        if (type == float.class) return 0f;
        return 0;
    }

    private static final class State {
        private final Kind kind;
        private final long jobKey;
        private final Map<String, Object> arguments = new LinkedHashMap<>();

        State(Kind kind, long jobKey) {
            this.kind = kind;
            this.jobKey = jobKey;
        }

        Call toCall() { return new Call(kind, jobKey, Map.copyOf(arguments)); }
    }
}
