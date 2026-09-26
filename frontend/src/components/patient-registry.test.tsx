import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PatientRegistry, patientDeletePhrase } from "./patient-registry";

const apiMocks = vi.hoisted(() => ({
  getPatients: vi.fn(),
  getDeletedPatients: vi.fn(),
  getPatient: vi.fn(),
  deletePatient: vi.fn(),
  restorePatient: vi.fn(),
  createAppointment: vi.fn(),
  assessAppointment: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  ...(await vi.importActual<typeof import("@/lib/api")>("@/lib/api")),
  ...apiMocks,
}));

const patientSummary = {
  id: "patient-1",
  name: "Mdm Lim Siew Hoon",
  nric: "S1234567A",
  postal_code: "640123",
  nmtr_percentage: 0.95,
  escort_required: true,
  last_visit: null,
  deleted_at: null,
};

const deletedPatientSummary = {
  ...patientSummary,
  id: "patient-deleted",
  deleted_at: "2026-09-17T10:00:00+08:00",
};

const patientDetail = {
  ...patientSummary,
  aic_registration_no: null,
  block: null,
  unit: null,
  street_name: null,
  address: null,
  contact_no: null,
  caregiver_name: null,
  co_payment: null,
  date_of_birth: null,
  nmts_effective_date: null,
  nmts_expired_date: null,
  date_of_entry: null,
  action_updated_date: null,
  lh_service_agreement: null,
  sw_service_agreement: null,
  wheelchair_required: false,
  walking_frame_required: false,
  caregiver_or_maid_available: null,
  gender: null,
  gender_preference: null,
  address_source: null,
  dialect: null,
  weight_kg: null,
  aic_mobility_status: "unknown" as const,
  lh_mobility_status: "unknown" as const,
};

const deletedPatientDetail = {
  ...patientDetail,
  id: "patient-deleted",
  deleted_at: "2026-09-17T10:00:00+08:00",
};

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.getPatients.mockResolvedValue([patientSummary]);
  apiMocks.getDeletedPatients.mockResolvedValue([deletedPatientSummary]);
  apiMocks.getPatient.mockResolvedValue(patientDetail);
  apiMocks.deletePatient.mockResolvedValue(undefined);
  apiMocks.restorePatient.mockResolvedValue(patientDetail);
});

describe("PatientRegistry", () => {
  it("requires the patient-name delete phrase before deleting", async () => {
    const user = userEvent.setup();
    apiMocks.getPatients
      .mockResolvedValueOnce([patientSummary])
      .mockResolvedValueOnce([]);

    render(<PatientRegistry />);
    await user.click(
      await screen.findByRole("button", { name: /Mdm Lim Siew Hoon/i }),
    );
    await user.click(await screen.findByRole("button", { name: "Delete patient" }));

    const dialog = screen.getByRole("dialog", {
      name: "Delete Mdm Lim Siew Hoon",
    });
    expect(within(dialog).getByText("WARNING")).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "Delete patient" }),
    ).toBeDisabled();

    await user.type(
      within(dialog).getByRole("textbox"),
      patientDeletePhrase(patientSummary.name).toLocaleUpperCase(),
    );
    await user.click(within(dialog).getByRole("button", { name: "Delete patient" }));

    await waitFor(() =>
      expect(apiMocks.deletePatient).toHaveBeenCalledWith("patient-1"),
    );
  });

  it("shows soft-deleted patients and restores them", async () => {
    const user = userEvent.setup();
    apiMocks.getPatient.mockResolvedValue(deletedPatientDetail);

    render(<PatientRegistry />);
    await user.click(await screen.findByRole("tab", { name: "Deleted" }));
    await user.click(
      await screen.findByRole("button", { name: /Mdm Lim Siew Hoon/i }),
    );

    expect(await screen.findByText("Restore to active registry")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restore patient" }));

    await waitFor(() =>
      expect(apiMocks.restorePatient).toHaveBeenCalledWith("patient-deleted"),
    );
  });
});
