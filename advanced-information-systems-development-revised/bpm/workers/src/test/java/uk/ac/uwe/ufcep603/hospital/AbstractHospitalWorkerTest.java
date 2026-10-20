package uk.ac.uwe.ufcep603.hospital;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import uk.ac.uwe.ufcep603.hospital.config.AppConfig;
import uk.ac.uwe.ufcep603.hospital.config.SimulatedFailureRegistry;
import uk.ac.uwe.ufcep603.hospital.support.DemoClock;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The error handling every worker inherits.
 *
 * <p>{@code AbstractHospitalWorker.handle} turns whatever {@code execute()} does into
 * one of three engine commands: complete the job, throw a BPMN error the model can
 * catch, or fail the job so the engine retries it. Getting that wrong is how a case
 * stops - and it was the single largest untested surface in the project, since the
 * 30 tests that existed all sat below this layer and never entered it.
 */
class AbstractHospitalWorkerTest {

    private static WorkerContext workerContext() {
        AppConfig config = AppConfig.load(new String[0]);
        return new WorkerContext(config, new SimulatedFailureRegistry(config), null,
                new DemoClock(config));
    }

    /** A worker whose behaviour each test decides, so the base class is what is under test. */
    private static final class StubWorker extends AbstractHospitalWorker {
        private final Map<String, Object> result;
        private final RuntimeException thrown;

        StubWorker(Map<String, Object> result, RuntimeException thrown) {
            super("test.job", workerContext(), null);
            this.result = result;
            this.thrown = thrown;
        }

        @Override
        protected Map<String, Object> execute(JobContext job) {
            if (thrown != null) {
                throw thrown;
            }
            return result;
        }
    }

    private static RecordingJobClient run(StubWorker worker, Map<String, Object> variables) {
        RecordingJobClient recorder = new RecordingJobClient();
        worker.handle((io.camunda.zeebe.client.api.worker.JobClient) recorder.client(),
                TestJob.job().type("test.job").variables(variables).retries(3).build());
        return recorder;
    }

    @Test
    @DisplayName("a worker that returns output completes the job and passes the output on")
    void outputBecomesACompletion() {
        Map<String, Object> output = new LinkedHashMap<>();
        output.put("requestValidated", true);
        output.put("validatedCycleCount", 4);

        RecordingJobClient.Call call = run(new StubWorker(output, null), Map.of()).only();

        assertEquals(RecordingJobClient.Kind.COMPLETE, call.kind());
        assertEquals(2251799814000001L, call.jobKey());
        @SuppressWarnings("unchecked")
        Map<String, Object> sent = (Map<String, Object>) call.argument("variables");
        assertEquals(Boolean.TRUE, sent.get("requestValidated"));
        assertEquals(4, sent.get("validatedCycleCount"));
    }

    @Test
    @DisplayName("a null output variable is dropped rather than sent to the engine")
    void nullOutputsAreDropped() {
        Map<String, Object> output = new LinkedHashMap<>();
        output.put("kept", "yes");
        output.put("dropped", null);

        RecordingJobClient.Call call = run(new StubWorker(output, null), Map.of()).only();

        @SuppressWarnings("unchecked")
        Map<String, Object> sent = (Map<String, Object>) call.argument("variables");
        assertEquals("yes", sent.get("kept"));
        assertFalse(sent.containsKey("dropped"),
                "Zeebe rejects a null variable, so the base class must not send one");
    }

    @Test
    @DisplayName("a BPMN error is thrown with its code, not turned into a failed job")
    void businessErrorBecomesAThrowError() {
        RecordingJobClient.Call call = run(
                new StubWorker(null, new BpmnErrorException("TREATMENT_REQUEST_UNAUTHORISED",
                        "no booking reference")),
                Map.of()).only();

        assertEquals(RecordingJobClient.Kind.THROW_ERROR, call.kind());
        assertEquals("TREATMENT_REQUEST_UNAUTHORISED", call.argument("errorCode"));
        assertTrue(String.valueOf(call.argument("errorMessage")).contains("no booking reference"));
    }

    @Test
    @DisplayName("any other exception fails the job so the engine can retry it")
    void otherFailuresFailTheJob() {
        RecordingJobClient.Call call = run(
                new StubWorker(null, new ValidationException("treatmentPlan", "missing")),
                Map.of()).only();

        assertEquals(RecordingJobClient.Kind.FAIL, call.kind());
        assertEquals(2, call.argument("retries"),
                "3 retries on the job means 2 left after this failure");
        assertNotNull(call.argument("errorMessage"));
    }

    @Test
    @DisplayName("a business error is never downgraded into a plain job failure")
    void businessErrorsAreNotSwallowed() {
        // The distinction matters: a thrown BPMN error follows the model's error
        // boundary and is handled; a failed job retries and eventually raises an
        // incident. Retyping one as the other changes what the engine does.
        RecordingJobClient.Call call = run(
                new StubWorker(null, new BpmnErrorException("REFERRAL_PACK_INCOMPLETE", "two missing")),
                Map.of()).only();

        assertTrue(call.kind() == RecordingJobClient.Kind.THROW_ERROR,
                "expected THROW_ERROR but the worker issued " + call.kind());
    }

    @Test
    @DisplayName("the job type the worker subscribes to is its own, plus any alias")
    void jobTypesCoverTheAlias() {
        StubWorker worker = new StubWorker(Map.of(), null);
        assertEquals(java.util.List.of("test.job"), worker.jobTypes());
        assertEquals("test.job", worker.jobType());
    }
}
