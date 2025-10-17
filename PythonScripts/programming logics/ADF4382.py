def execute_macro(client):
    client.ContextPath = "\System\Subsystem_1\ADF4382 Board\ADF4382"
    client.SetIntParameter("PD_RFOUT2", "0", "-1")
    client.SetBoolParameter("PD_SYNC", "False", "-1")
    client.Run("@ApplyAllSettings")