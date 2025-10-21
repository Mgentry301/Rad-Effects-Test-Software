def execute_macro(client):
    client.ContextPath = "\System\Subsystem_1\ADMV8827 Board\ADMV8827"
    client.SetByteParameter("virtual-parameter-hpf3_state", "3", "-1") 
    client.SetByteParameter("virtual-parameter-lpf3_state", "3", "-1")
    client.SetIntParameter("SW_SELECT", "2", "-1")
    client.Run("@ApplySettings")