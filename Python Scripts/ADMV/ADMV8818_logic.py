def logic(client):
    """Custom logic for ADMV8818."""
    client.ContextPath = "\System\Subsystem_1\ADMV8818 Board\ADMV8818"
    client.SetIntParameter("SW_IN_WR1", "1", "-1")
    client.SetIntParameter("SW_OUT_WR1", "1", "-1")
    client.SetByteParameter("LPF_WR1", "15", "-1")
    client.Run("@Wizards")
    client.SetIntParameter("virtual-parameter-displayed-rfin-switch-position", "3", "-1")
    client.SetIntParameter("virtual-parameter-displayed-rfout-switch-position", "4", "-1")
    client.SetByteParameter("virtual-parameter-displayed-lpf", "0", "-1")
    client.SetByteParameter("virtual-parameter-displayed-hpf", "0", "-1")
    print("Custom logic for ADMV8818 executed.")