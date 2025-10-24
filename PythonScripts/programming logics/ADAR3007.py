def execute_macro(client):
    client.AddByComponentId("ADAR3006Board")
    client.ContextPath = "\System\Subsystem_1\ADAR3006 Board\ADAR3006"
    client.NavigateToPath("Root::System.Subsystem_1.ADAR3006 Board.ADAR3006")
    client.Run("@SoftReset")
    client.SetBoolParameter("update_spi_pinb_ctl", "True", "-1")
    client.Run("@PinOrSpiControl")
    client.Run("@AllBeamUpdate")
