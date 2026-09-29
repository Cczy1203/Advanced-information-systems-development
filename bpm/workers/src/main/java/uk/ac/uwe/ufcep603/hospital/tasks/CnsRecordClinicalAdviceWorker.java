package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.Map;

/**
 * {@code cns.record-clinical-advice} - Clinical Nurse Specialist Team, "Record the advice given".
 *
 * <p>Only a qualified clinical professional gives advice here, so the record has to name who advised
 * and what was said. Both are required: a blank {@code clinicalAdviceSummary} or {@code advisedBy}
 * fails the job with a message naming the missing variable instead of writing a hollow record.
 */
public final class CnsRecordClinicalAdviceWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "cns.record-clinical-advice";

    public CnsRecordClinicalAdviceWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String enquiryRef = job.requireFirst("enquiryRef", "enquiryRef", "enquiryReference", "enquiryId",
                "enquiryNumber");
        String summary = job.requireFirst("clinicalAdviceSummary",
                "clinicalAdviceSummary", "adviceSummary", "clinicalAdvice", "adviceGiven", "advice");
        String advisedBy = job.requireFirst("advisedBy",
                "advisedBy", "advisedByClinician", "clinicianName", "decidingClinician", "nurseSpecialist");

        Map<String, Object> output = job.output();
        output.put("clinicalAdviceRecordedRef", Ids.reference("ADV", enquiryRef, summary, advisedBy));
        output.put("adviceRecordedAt", context().clock().timestamp());
        output.put("clinicalAdviceAdvisedBy", advisedBy);
        output.put("clinicalAdviceEnquiryRef", enquiryRef);
        return output;
    }
}
