def execute_macro(client):
    client.ContextPath = "\System\Subsystem_1\ADMV8809 Board\ADMV8809"
    client.SetIntParameter("SW_SELECT", "2", "-1")
    client.SetByteParameter("virtual-parameter-lpf3_state", "0", "-1")
    #write to LUT table
    client.SetRegister("38", "7", "-1")
    client.SetRegister("39", "255", "-1")
    client.Run("@ApplySettings")