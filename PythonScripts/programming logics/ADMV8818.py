def execute_macro(client):
    client.AddByComponentId("ADMV8818Board")
    client.NavigateToPath("Root::System")
    client.ContextPath = "\System\Subsystem_1\ADMV8818 Board"
    client.Run("@DefaultView")
    client.ContextPath = "\System\Subsystem_1\ADMV8818 Board\ADMV8818"
    client.SetByteParameter("HPF_WR1", "0", "-1")
    client.Run("@Wizards")
    client.SetIntParameter("virtual-parameter-displayed-rfin-switch-position", "3", "-1")
    client.SetByteParameter("virtual-parameter-displayed-hpf", "7", "-1")
    client.SetIntParameter("virtual-parameter-displayed-rfout-switch-position", "3", "-1")
    client.SetByteParameter("virtual-parameter-displayed-lpf", "7", "-1")
    print("done")