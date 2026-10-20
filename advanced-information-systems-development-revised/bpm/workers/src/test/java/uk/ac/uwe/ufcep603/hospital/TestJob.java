package uk.ac.uwe.ufcep603.hospital;

import io.camunda.zeebe.client.api.response.ActivatedJob;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * An {@link ActivatedJob} with no engine behind it.
 *
 * <p>The worker layer had no tests at all before this: the 30 that existed covered
 * {@code DateRuleValidator}, {@code NhsNumber}, {@code HospitalStore} and
 * {@code AccessControl}, and every one of the 36 {@code execute()} methods - and the
 * base class that turns their result into a complete, a BPMN error or a failure -
 * was unexercised. That is the layer where a wrong variable name or a mis-typed
 * error code stops a case, so it is the layer worth a fake.
 *
 * <p>Only the seven methods {@link JobContext} and
 * {@link AbstractHospitalWorker#handle} actually call are implemented; the rest of
 * the interface is answered with a null rather than a plausible-looking default, so
 * an accidental new dependency on the job object shows up as a failure here.
 */
final class TestJob implements ActivatedJob {

    private final long key;
    private final int retries;
    private final String type;
    private final String elementId;
    private final Map<String, Object> variables;
    private final Map<String, String> customHeaders;

    private TestJob(long key, int retries, String type, String elementId,
                    Map<String, Object> variables, Map<String, String> customHeaders) {
        this.key = key;
        this.retries = retries;
        this.type = type;
        this.elementId = elementId;
        this.variables = new LinkedHashMap<>(variables);
        this.customHeaders = new LinkedHashMap<>(customHeaders);
    }

    static Builder job() {
        return new Builder();
    }

    static final class Builder {
        private long key = 2251799814000001L;
        private int retries = 3;
        private String type = "test.job";
        private String elementId = "TEST_Service_Task";
        private Map<String, Object> variables = new LinkedHashMap<>();
        private Map<String, String> customHeaders = new LinkedHashMap<>();

        Builder key(long value) { this.key = value; return this; }
        Builder retries(int value) { this.retries = value; return this; }
        Builder type(String value) { this.type = value; return this; }
        Builder elementId(String value) { this.elementId = value; return this; }
        Builder variables(Map<String, Object> value) { this.variables = value; return this; }
        Builder customHeaders(Map<String, String> value) { this.customHeaders = value; return this; }

        TestJob build() {
            return new TestJob(key, retries, type, elementId, variables, customHeaders);
        }
    }

    // ---- the seven the worker layer actually reads -------------------------------

    @Override public long getKey() { return key; }
    @Override public int getRetries() { return retries; }
    @Override public String getType() { return type; }
    @Override public String getElementId() { return elementId; }
    @Override public Map<String, Object> getVariablesAsMap() { return variables; }
    @Override public Map<String, String> getCustomHeaders() { return customHeaders; }
    @Override public String getBpmnProcessId() { return "hospital-patient-pathway"; }

    // ---- deliberately not faked --------------------------------------------------

    @Override public long getProcessInstanceKey() { return 2251799814000000L; }
    @Override public int getProcessDefinitionVersion() { return 0; }
    @Override public long getProcessDefinitionKey() { return 0; }
    @Override public long getElementInstanceKey() { return 0; }
    @Override public String getWorker() { return null; }
    @Override public long getDeadline() { return 0; }
    @Override public String getVariables() { return "{}"; }
    @Override public <T> T getVariablesAsType(Class<T> type) { return null; }
    @Override public Object getVariable(String name) { return variables.get(name); }
    @Override public io.camunda.zeebe.client.api.response.UserTaskProperties getUserTask() { return null; }
    @Override public String getTenantId() { return "<default>"; }
    @Override public String toJson() { return "{}"; }
}
