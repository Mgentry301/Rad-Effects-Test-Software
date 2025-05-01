<?xml version='1.0' encoding='UTF-8'?>
<Project Type="Project" LVVersion="19008000">
	<Item Name="My Computer" Type="My Computer">
		<Property Name="NI.SortType" Type="Int">3</Property>
		<Property Name="server.app.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.control.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.tcp.enabled" Type="Bool">false</Property>
		<Property Name="server.tcp.port" Type="Int">0</Property>
		<Property Name="server.tcp.serviceName" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.tcp.serviceName.default" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.vi.callsEnabled" Type="Bool">true</Property>
		<Property Name="server.vi.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="specify.custom.address" Type="Bool">false</Property>
		<Item Name="Controls" Type="Folder">
			<Item Name="DataBlockControl.ctl" Type="VI" URL="../Controls/DataBlockControl.ctl"/>
			<Item Name="OscilloscopeBlockControl.ctl" Type="VI" URL="../Controls/OscilloscopeBlockControl.ctl"/>
			<Item Name="PlotColorArray.ctl" Type="VI" URL="../Controls/PlotColorArray.ctl"/>
			<Item Name="PowerBlockControl.ctl" Type="VI" URL="../Controls/PowerBlockControl.ctl"/>
			<Item Name="QueueDataControl.ctl" Type="VI" URL="../Controls/QueueDataControl.ctl"/>
			<Item Name="QueueDataControl_V2.ctl" Type="VI" URL="../Controls/QueueDataControl_V2.ctl"/>
			<Item Name="QueueDataControl_V3.ctl" Type="VI" URL="../Controls/QueueDataControl_V3.ctl"/>
			<Item Name="RFBlockControl.ctl" Type="VI" URL="../Controls/RFBlockControl.ctl"/>
		</Item>
		<Item Name="DataCollectionSubVI" Type="Folder">
			<Property Name="NI.SortType" Type="Int">3</Property>
			<Item Name="Change_RunInfo.vi" Type="VI" URL="../DataCollectionSubVI/Change_RunInfo.vi"/>
			<Item Name="Change_RunInfo_V2.vi" Type="VI" URL="../DataCollectionSubVI/Change_RunInfo_V2.vi"/>
			<Item Name="Convert_RunInfoCluster_2_RunInfoStringList.vi" Type="VI" URL="../DataCollectionSubVI/Convert_RunInfoCluster_2_RunInfoStringList.vi"/>
			<Item Name="DataFileNode_Entry_V2.vi" Type="VI" URL="../DataCollectionSubVI/DataFileNode_Entry_V2.vi"/>
			<Item Name="DataFileNode_Entry_V3.vi" Type="VI" URL="../DataCollectionSubVI/DataFileNode_Entry_V3.vi"/>
			<Item Name="DataFileNode_Entry_V4.vi" Type="VI" URL="../DataCollectionSubVI/DataFileNode_Entry_V4.vi"/>
			<Item Name="DataFileNode_Entry_V5.vi" Type="VI" URL="../DataCollectionSubVI/DataFileNode_Entry_V5.vi"/>
			<Item Name="DCPower_CreateOutputArray.vi" Type="VI" URL="../DataCollectionSubVI/DCPower_CreateOutputArray.vi"/>
			<Item Name="DCPower_CreateOutputArray_V3.vi" Type="VI" URL="../DataCollectionSubVI/DCPower_CreateOutputArray_V3.vi"/>
			<Item Name="DCPower_ParameterCreation.vi" Type="VI" URL="../DataCollectionSubVI/DCPower_ParameterCreation.vi"/>
			<Item Name="Fetch&amp;Process_Measurements.vi" Type="VI" URL="../DataCollectionSubVI/Fetch&amp;Process_Measurements.vi"/>
			<Item Name="Fetch&amp;Process_Measurements_V2.vi" Type="VI" URL="../DataCollectionSubVI/Fetch&amp;Process_Measurements_V2.vi"/>
			<Item Name="Fetch&amp;Process_Measurements_V3.vi" Type="VI" URL="../DataCollectionSubVI/Fetch&amp;Process_Measurements_V3.vi"/>
			<Item Name="Fetch&amp;Process_Measurements_V4.vi" Type="VI" URL="../DataCollectionSubVI/Fetch&amp;Process_Measurements_V4.vi"/>
			<Item Name="FilePathCreation_DCPower_V2.vi" Type="VI" URL="../DataCollectionSubVI/FilePathCreation_DCPower_V2.vi"/>
			<Item Name="ReadDataFile_V1.vi" Type="VI" URL="../DataCollectionSubVI/ReadDataFile_V1.vi"/>
			<Item Name="ReadDataFile_V2.vi" Type="VI" URL="../DataCollectionSubVI/ReadDataFile_V2.vi"/>
			<Item Name="SupplementalDataFileNode_Entry_V2.vi" Type="VI" URL="../DataCollectionSubVI/SupplementalDataFileNode_Entry_V2.vi"/>
			<Item Name="SupplementalDataFileNode_Entry_V3.vi" Type="VI" URL="../DataCollectionSubVI/SupplementalDataFileNode_Entry_V3.vi"/>
		</Item>
		<Item Name="OscilloscopeSubVI" Type="Folder"/>
		<Item Name="Panels" Type="Folder">
			<Item Name="DataBlock_Panel_Rev11.vi" Type="VI" URL="../Panels/DataBlock_Panel_Rev11.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v2.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v2.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v3.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v3.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v4.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v4.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v5.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v5.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v6.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v6.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v7.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v7.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v8.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v8.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v9.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v9.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v10.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v10.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v11.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v11.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v12.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v12.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v13.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v13.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v14.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v14.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v15.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v15.vi"/>
			<Item Name="SubPanel_DataCollection_Rev11_v16.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v16.vi"/>
			<Item Name="SubPanel_Oscilloscope_Block_Rev11.vi" Type="VI" URL="../Panels/SubPanel_Oscilloscope_Block_Rev11.vi"/>
			<Item Name="SubPanel_Oscilloscope_Block_Rev11_v2.vi" Type="VI" URL="../Panels/SubPanel_Oscilloscope_Block_Rev11_v2.vi"/>
			<Item Name="SubPanel_PowerConfiguration_Rev11.vi" Type="VI" URL="../Panels/SubPanel_PowerConfiguration_Rev11.vi"/>
			<Item Name="SubPanel_PowerConfiguration_Rev11_v2.vi" Type="VI" URL="../Panels/SubPanel_PowerConfiguration_Rev11_v2.vi"/>
			<Item Name="SubPanel_PowerConfiguration_Rev11_v3.vi" Type="VI" URL="../Panels/SubPanel_PowerConfiguration_Rev11_v3.vi"/>
			<Item Name="SubPanel_PowerConfiguration_Rev11_v4.vi" Type="VI" URL="../Panels/SubPanel_PowerConfiguration_Rev11_v4.vi"/>
			<Item Name="SubPanel_RFBlock_Panel_Rev11.vi" Type="VI" URL="../Panels/SubPanel_RFBlock_Panel_Rev11.vi"/>
			<Item Name="SubPanel_RFBlock_Panel_Rev11_v2.vi" Type="VI" URL="../Panels/SubPanel_RFBlock_Panel_Rev11_v2.vi"/>
		</Item>
		<Item Name="PowerSubVI" Type="Folder">
			<Item Name="DCPower_ConfigureInstrument.vi" Type="VI" URL="../PowerSubVI/DCPower_ConfigureInstrument.vi"/>
			<Item Name="DCPower_ConfigureInstrument_V2.vi" Type="VI" URL="../PowerSubVI/DCPower_ConfigureInstrument_V2.vi"/>
			<Item Name="DCPower_CurrentLimit&amp;MeasureRecordReadout.vi" Type="VI" URL="../PowerSubVI/DCPower_CurrentLimit&amp;MeasureRecordReadout.vi"/>
			<Item Name="DCPower_CurrentLimitConfiguration.vi" Type="VI" URL="../PowerSubVI/DCPower_CurrentLimitConfiguration.vi"/>
			<Item Name="DCPower_InstrumentArrayCheck.vi" Type="VI" URL="../PowerSubVI/DCPower_InstrumentArrayCheck.vi"/>
			<Item Name="DCPower_MeasureRecordConfiguration.vi" Type="VI" URL="../PowerSubVI/DCPower_MeasureRecordConfiguration.vi"/>
			<Item Name="DCPower_VoltageConfiguration.vi" Type="VI" URL="../PowerSubVI/DCPower_VoltageConfiguration.vi"/>
			<Item Name="VISA_Keithley2230G_ConfigureInstrument_V1.vi" Type="VI" URL="../PowerSubVI/VISA_Keithley2230G_ConfigureInstrument_V1.vi"/>
		</Item>
		<Item Name="RFConfigSubVI" Type="Folder">
			<Item Name="RFConfig_SubVI_HMCT22##_PowerOnOff.vi" Type="VI" URL="../RFConfigSubVI/RFConfig_SubVI_HMCT22##_PowerOnOff.vi"/>
			<Item Name="RFConfig_SubVI_HMCT22##_SettingConfiguration.vi" Type="VI" URL="../RFConfigSubVI/RFConfig_SubVI_HMCT22##_SettingConfiguration.vi"/>
			<Item Name="SubPanel_RFBlock_Panel_Rev11_v3.vi" Type="VI" URL="../Panels/SubPanel_RFBlock_Panel_Rev11_v3.vi"/>
		</Item>
		<Item Name="StandAloneTransientSubVI" Type="Folder" URL="../StandAloneTransientSubVI">
			<Property Name="NI.DISK" Type="Bool">true</Property>
		</Item>
		<Item Name="Utility" Type="Folder">
			<Item Name="Change_RunNumber.vi" Type="VI" URL="../Utility/Change_RunNumber.vi"/>
			<Item Name="CreatingName_UsuallyInstrument.vi" Type="VI" URL="../Utility/CreatingName_UsuallyInstrument.vi"/>
			<Item Name="DoubleArray2StringArray.vi" Type="VI" URL="../DoubleArray2StringArray.vi"/>
			<Item Name="Determining_Change_RunNumber.vi" Type="VI" URL="../Utility/Determining_Change_RunNumber.vi"/>
			<Item Name="ReadTextFiles2ExcelCSV.vi" Type="VI" URL="../Utility/ReadTextFiles2ExcelCSV.vi"/>
			<Item Name="ReadTextFiles2ExcelCSV_Subvi.vi" Type="VI" URL="../Utility/ReadTextFiles2ExcelCSV_Subvi.vi"/>
			<Item Name="StringArray2StringList.vi" Type="VI" URL="../Utility/StringArray2StringList.vi"/>
			<Item Name="Convert_InstrumentReferenceArray_2_ChannelReferenceArray.vi" Type="VI" URL="../Utility/Convert_InstrumentReferenceArray_2_ChannelReferenceArray.vi"/>
			<Item Name="StandAlone_CloseSessions.vi" Type="VI" URL="../Utility/StandAlone_CloseSessions.vi"/>
		</Item>
		<Item Name="IndependentVISApowerDataCollection.vi" Type="VI" URL="../IndependentVISApowerDataCollection.vi"/>
		<Item Name="SEE_PXI_TopBench_Rev11.vi" Type="VI" URL="../SEE_PXI_TopBench_Rev11.vi"/>
		<Item Name="StandAlone_ReadData.vi" Type="VI" URL="../StandAlone_ReadData.vi"/>
		<Item Name="StandAlone_TransientDataCollection.vi" Type="VI" URL="../StandAlone_TransientDataCollection.vi"/>
		<Item Name="StandAlone_TransientDataRead.vi" Type="VI" URL="../StandAlone_TransientDataRead.vi"/>
		<Item Name="TEST_DCPOWER_READING_MULTI-INSTRUMENT_V7.vi" Type="VI" URL="../../DataCollectionRev9/TEST_DCPOWER_READING_MULTI-INSTRUMENT_V7.vi"/>
		<Item Name="StandAlone_TransientDataCollection_Overhaul.vi" Type="VI" URL="../StandAlone_TransientDataCollection_Overhaul.vi"/>
		<Item Name="Dependencies" Type="Dependencies">
			<Item Name="instr.lib" Type="Folder">
				<Item Name="niDCPower Abort With Channels.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Abort With Channels.vi"/>
				<Item Name="niDCPower Aperture Time Units.ctl" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Aperture Time Units.ctl"/>
				<Item Name="niDCPower Close.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Close.vi"/>
				<Item Name="niDCPower Commit With Channels.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Commit With Channels.vi"/>
				<Item Name="niDCPower Configure Aperture Time.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Configure Aperture Time.vi"/>
				<Item Name="niDCPower Configure Current Limit Range.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Configure Current Limit Range.vi"/>
				<Item Name="niDCPower Configure Current Limit.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Configure Current Limit.vi"/>
				<Item Name="niDCPower Configure Voltage Level.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Configure Voltage Level.vi"/>
				<Item Name="niDCPower Current Limit Behavior.ctl" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Current Limit Behavior.ctl"/>
				<Item Name="niDCPower Fetch Multiple.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Fetch Multiple.vi"/>
				<Item Name="niDCPower Initialize With Independent Channels.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Initialize With Independent Channels.vi"/>
				<Item Name="niDCPower Initiate With Channels.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower Initiate With Channels.vi"/>
				<Item Name="niDCPower IVI Error Converter.vi" Type="VI" URL="/&lt;instrlib&gt;/niDCPower/nidcpower.llb/niDCPower IVI Error Converter.vi"/>
				<Item Name="niDigital Burst Pattern (Burst Only).vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Burst Pattern (Burst Only).vi"/>
				<Item Name="niDigital Burst Pattern (Pass Fail).vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Burst Pattern (Pass Fail).vi"/>
				<Item Name="niDigital Burst Pattern.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Burst Pattern.vi"/>
				<Item Name="niDigital Get Site Pass Fail.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Get Site Pass Fail.vi"/>
				<Item Name="niDigital IVI Error Converter.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital IVI Error Converter.vi"/>
				<Item Name="niDigital Output Function.ctl" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Output Function.ctl"/>
				<Item Name="niDigital PPMU Configure Current Limit Range.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital PPMU Configure Current Limit Range.vi"/>
				<Item Name="niDigital PPMU Configure Output Function.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital PPMU Configure Output Function.vi"/>
				<Item Name="niDigital PPMU Configure Voltage Level.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital PPMU Configure Voltage Level.vi"/>
				<Item Name="niDigital PPMU Source.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital PPMU Source.vi"/>
				<Item Name="niDigital Select Function.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Select Function.vi"/>
				<Item Name="niDigital Selected Function.ctl" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Selected Function.ctl"/>
				<Item Name="niDMM Close.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Close.vi"/>
				<Item Name="niDMM Config Measurement.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Config Measurement.vi"/>
				<Item Name="niDMM Configure Measurement Absolute.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Configure Measurement Absolute.vi"/>
				<Item Name="niDMM Configure Measurement Digits.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Configure Measurement Digits.vi"/>
				<Item Name="niDMM Configure Trigger.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Configure Trigger.vi"/>
				<Item Name="niDMM Fetch.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Fetch.vi"/>
				<Item Name="niDMM Function To IVI Constant.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Function To IVI Constant.vi"/>
				<Item Name="niDMM Function.ctl" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Function.ctl"/>
				<Item Name="niDMM Initialize.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Initialize.vi"/>
				<Item Name="niDMM Initiate.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Initiate.vi"/>
				<Item Name="niDMM IVI Error Converter.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM IVI Error Converter.vi"/>
				<Item Name="niDMM Resolution in Digits.ctl" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Resolution in Digits.ctl"/>
				<Item Name="niDMM Trigger Source To IVI Constant.vi" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Trigger Source To IVI Constant.vi"/>
				<Item Name="niDMM Trigger.ctl" Type="VI" URL="/&lt;instrlib&gt;/niDMM/nidmm.llb/niDMM Trigger.ctl"/>
				<Item Name="niScope Abort.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Abort.vi"/>
				<Item Name="niScope Close.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/niScope Close.vi"/>
				<Item Name="niScope Configure Chan Characteristics.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Vertical/niScope Configure Chan Characteristics.vi"/>
				<Item Name="niScope Configure Horizontal Timing.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Horizontal/niScope Configure Horizontal Timing.vi"/>
				<Item Name="niScope Configure Trigger (poly).vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger (poly).vi"/>
				<Item Name="niScope Configure Trigger Digital.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Digital.vi"/>
				<Item Name="niScope Configure Trigger Edge.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Edge.vi"/>
				<Item Name="niScope Configure Trigger Glitch.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Glitch.vi"/>
				<Item Name="niScope Configure Trigger Hysteresis.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Hysteresis.vi"/>
				<Item Name="niScope Configure Trigger Immediate.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Immediate.vi"/>
				<Item Name="niScope Configure Trigger Runt.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Runt.vi"/>
				<Item Name="niScope Configure Trigger Software.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Software.vi"/>
				<Item Name="niScope Configure Trigger Width.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Width.vi"/>
				<Item Name="niScope Configure Trigger Window.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Trigger Window.vi"/>
				<Item Name="niScope Configure Vertical.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Vertical/niScope Configure Vertical.vi"/>
				<Item Name="niScope Configure Video Trigger.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Configure/Trigger/niScope Configure Video Trigger.vi"/>
				<Item Name="niScope Fetch (poly).vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch (poly).vi"/>
				<Item Name="niScope Fetch Binary 8.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch Binary 8.vi"/>
				<Item Name="niScope Fetch Binary 16.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch Binary 16.vi"/>
				<Item Name="niScope Fetch Binary 32.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch Binary 32.vi"/>
				<Item Name="niScope Fetch Cluster Complex Double.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch Cluster Complex Double.vi"/>
				<Item Name="niScope Fetch Cluster.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch Cluster.vi"/>
				<Item Name="niScope Fetch Complex Double.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch Complex Double.vi"/>
				<Item Name="niScope Fetch Complex WDT.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch Complex WDT.vi"/>
				<Item Name="niScope Fetch Error Chain.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch Error Chain.vi"/>
				<Item Name="niScope Fetch WDT.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch WDT.vi"/>
				<Item Name="niScope Fetch.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Fetch.vi"/>
				<Item Name="niScope Get Session Reference.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Utility/niScope Get Session Reference.vi"/>
				<Item Name="niScope glitch condition.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope glitch condition.ctl"/>
				<Item Name="niScope Initialize.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/niScope Initialize.vi"/>
				<Item Name="niScope Initiate Acquisition.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Initiate Acquisition.vi"/>
				<Item Name="niScope LabVIEW Error.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Utility/niScope LabVIEW Error.vi"/>
				<Item Name="niScope Multi Fetch Binary 8.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch Binary 8.vi"/>
				<Item Name="niScope Multi Fetch Binary 16.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch Binary 16.vi"/>
				<Item Name="niScope Multi Fetch Binary 32.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch Binary 32.vi"/>
				<Item Name="niScope Multi Fetch Cluster Complex Double.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch Cluster Complex Double.vi"/>
				<Item Name="niScope Multi Fetch Cluster.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch Cluster.vi"/>
				<Item Name="niScope Multi Fetch Complex Double.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch Complex Double.vi"/>
				<Item Name="niScope Multi Fetch Complex WDT.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch Complex WDT.vi"/>
				<Item Name="niScope Multi Fetch WDT.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch WDT.vi"/>
				<Item Name="niScope Multi Fetch.vi" Type="VI" URL="/&lt;instrlib&gt;/niScope/Acquire/Fetch/niScope Multi Fetch.vi"/>
				<Item Name="niScope polarity.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope polarity.ctl"/>
				<Item Name="niScope signal format.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope signal format.ctl"/>
				<Item Name="niScope timestamp type.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope timestamp type.ctl"/>
				<Item Name="niScope trigger coupling.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope trigger coupling.ctl"/>
				<Item Name="niScope trigger polarity.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope trigger polarity.ctl"/>
				<Item Name="niScope trigger slope.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope trigger slope.ctl"/>
				<Item Name="niScope trigger source digital.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope trigger source digital.ctl"/>
				<Item Name="niScope trigger source.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope trigger source.ctl"/>
				<Item Name="niScope trigger window mode.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope trigger window mode.ctl"/>
				<Item Name="niScope tv event.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope tv event.ctl"/>
				<Item Name="niScope vertical coupling.ctl" Type="VI" URL="/&lt;instrlib&gt;/niScope/Controls/niScope vertical coupling.ctl"/>
				<Item Name="niDigital Get Session Reference.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Get Session Reference.vi"/>
				<Item Name="niDigital Close.vi" Type="VI" URL="/&lt;instrlib&gt;/niDigital/niDigital.llb/niDigital Close.vi"/>
			</Item>
			<Item Name="vi.lib" Type="Folder">
				<Item Name="BuildHelpPath.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/BuildHelpPath.vi"/>
				<Item Name="Check Special Tags.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Check Special Tags.vi"/>
				<Item Name="Clear Errors.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Clear Errors.vi"/>
				<Item Name="Close File+.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Close File+.vi"/>
				<Item Name="compatReadText.vi" Type="VI" URL="/&lt;vilib&gt;/_oldvers/_oldvers.llb/compatReadText.vi"/>
				<Item Name="Convert property node font to graphics font.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Convert property node font to graphics font.vi"/>
				<Item Name="Details Display Dialog.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Details Display Dialog.vi"/>
				<Item Name="DialogType.ctl" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/DialogType.ctl"/>
				<Item Name="DialogTypeEnum.ctl" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/DialogTypeEnum.ctl"/>
				<Item Name="Error Code Database.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Error Code Database.vi"/>
				<Item Name="ErrWarn.ctl" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/ErrWarn.ctl"/>
				<Item Name="eventvkey.ctl" Type="VI" URL="/&lt;vilib&gt;/event_ctls.llb/eventvkey.ctl"/>
				<Item Name="ex_CorrectErrorChain.vi" Type="VI" URL="/&lt;vilib&gt;/express/express shared/ex_CorrectErrorChain.vi"/>
				<Item Name="Find First Error.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Find First Error.vi"/>
				<Item Name="Find Tag.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Find Tag.vi"/>
				<Item Name="Format Message String.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Format Message String.vi"/>
				<Item Name="General Error Handler Core CORE.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/General Error Handler Core CORE.vi"/>
				<Item Name="General Error Handler.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/General Error Handler.vi"/>
				<Item Name="Get String Text Bounds.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Get String Text Bounds.vi"/>
				<Item Name="Get Text Rect.vi" Type="VI" URL="/&lt;vilib&gt;/picture/picture.llb/Get Text Rect.vi"/>
				<Item Name="GetHelpDir.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/GetHelpDir.vi"/>
				<Item Name="GetRTHostConnectedProp.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/GetRTHostConnectedProp.vi"/>
				<Item Name="Longest Line Length in Pixels.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Longest Line Length in Pixels.vi"/>
				<Item Name="LVBoundsTypeDef.ctl" Type="VI" URL="/&lt;vilib&gt;/Utility/miscctls.llb/LVBoundsTypeDef.ctl"/>
				<Item Name="LVRectTypeDef.ctl" Type="VI" URL="/&lt;vilib&gt;/Utility/miscctls.llb/LVRectTypeDef.ctl"/>
				<Item Name="NI_AALBase.lvlib" Type="Library" URL="/&lt;vilib&gt;/Analysis/NI_AALBase.lvlib"/>
				<Item Name="Not Found Dialog.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Not Found Dialog.vi"/>
				<Item Name="Open File+.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Open File+.vi"/>
				<Item Name="Read Delimited Spreadsheet (DBL).vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Read Delimited Spreadsheet (DBL).vi"/>
				<Item Name="Read Delimited Spreadsheet (I64).vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Read Delimited Spreadsheet (I64).vi"/>
				<Item Name="Read Delimited Spreadsheet (string).vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Read Delimited Spreadsheet (string).vi"/>
				<Item Name="Read Delimited Spreadsheet.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Read Delimited Spreadsheet.vi"/>
				<Item Name="Read File+ (string).vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Read File+ (string).vi"/>
				<Item Name="Read Lines From File (with error IO).vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Read Lines From File (with error IO).vi"/>
				<Item Name="Search and Replace Pattern.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Search and Replace Pattern.vi"/>
				<Item Name="Set Bold Text.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Set Bold Text.vi"/>
				<Item Name="Set String Value.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Set String Value.vi"/>
				<Item Name="Simple Error Handler.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Simple Error Handler.vi"/>
				<Item Name="subDisplayMessage.vi" Type="VI" URL="/&lt;vilib&gt;/express/express output/DisplayMessageBlock.llb/subDisplayMessage.vi"/>
				<Item Name="subTimeDelay.vi" Type="VI" URL="/&lt;vilib&gt;/express/express execution control/TimeDelayBlock.llb/subTimeDelay.vi"/>
				<Item Name="TagReturnType.ctl" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/TagReturnType.ctl"/>
				<Item Name="Three Button Dialog CORE.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Three Button Dialog CORE.vi"/>
				<Item Name="Three Button Dialog.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Three Button Dialog.vi"/>
				<Item Name="Trim Whitespace.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Trim Whitespace.vi"/>
				<Item Name="whitespace.ctl" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/whitespace.ctl"/>
				<Item Name="Write Delimited Spreadsheet (DBL).vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Write Delimited Spreadsheet (DBL).vi"/>
				<Item Name="Write Delimited Spreadsheet (I64).vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Write Delimited Spreadsheet (I64).vi"/>
				<Item Name="Write Delimited Spreadsheet (string).vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Write Delimited Spreadsheet (string).vi"/>
				<Item Name="Write Delimited Spreadsheet.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Write Delimited Spreadsheet.vi"/>
				<Item Name="Write Spreadsheet String.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/file.llb/Write Spreadsheet String.vi"/>
			</Item>
			<Item Name="Bitfield and Data.ctl" Type="VI" URL="/Users/Aerolab1/Documents/LabVIEW Data/2019(64-bit)/Projects/TAMU2024/Scripts/KBTR/Independent Digital Control/Bitfield and Data.ctl"/>
			<Item Name="Digital - Cleanup.vi" Type="VI" URL="/Users/Aerolab1/Documents/LabVIEW Data/2019(64-bit)/Projects/TAMU2024/Scripts/KBTR/Independent Digital Control/Digital - Cleanup.vi"/>
			<Item Name="Digital - Initialize.vi" Type="VI" URL="/Users/Aerolab1/Documents/LabVIEW Data/2019(64-bit)/Projects/TAMU2024/Scripts/KBTR/Independent Digital Control/Digital - Initialize.vi"/>
			<Item Name="Digital - KBTR - Determine Bitfield Data to Write.vi" Type="VI" URL="/Users/Aerolab1/Documents/LabVIEW Data/2019(64-bit)/Projects/TAMU2024/Scripts/KBTR/Independent Digital Control/Digital - KBTR - Determine Bitfield Data to Write.vi"/>
			<Item Name="Digital - Read Configuration Register.vi" Type="VI" URL="/Users/Aerolab1/Documents/LabVIEW Data/2019(64-bit)/Projects/TAMU2024/Scripts/KBTR/Independent Digital Control/Digital - Read Configuration Register.vi"/>
			<Item Name="Digital - Write Current Beam.vi" Type="VI" URL="/Users/Aerolab1/Documents/LabVIEW Data/2019(64-bit)/Projects/TAMU2024/Scripts/KBTR/Independent Digital Control/Digital - Write Current Beam.vi"/>
			<Item Name="InitialFileFolderCreation_V2.vi" Type="VI" URL="../DataCollectionSubVI/InitialFileFolderCreation_V2.vi"/>
			<Item Name="Initialize_VISA_PowerSupplies_Keithley2230G_V1.vi" Type="VI" URL="../PowerConfig/Initialize_VISA_PowerSupplies_Keithley2230G_V1.vi"/>
			<Item Name="lvanlys.dll" Type="Document" URL="/&lt;resource&gt;/lvanlys.dll"/>
			<Item Name="nidcpower_64.dll" Type="Document" URL="nidcpower_64.dll">
				<Property Name="NI.PreserveRelativePath" Type="Bool">true</Property>
			</Item>
			<Item Name="niDigital_64.dll" Type="Document" URL="niDigital_64.dll">
				<Property Name="NI.PreserveRelativePath" Type="Bool">true</Property>
			</Item>
			<Item Name="nidmm_64.dll" Type="Document" URL="nidmm_64.dll">
				<Property Name="NI.PreserveRelativePath" Type="Bool">true</Property>
			</Item>
			<Item Name="niScope_64.dll" Type="Document" URL="niScope_64.dll">
				<Property Name="NI.PreserveRelativePath" Type="Bool">true</Property>
			</Item>
			<Item Name="SubPanel_DataCollection_Rev11_v17.vi" Type="VI" URL="../Panels/SubPanel_DataCollection_Rev11_v17.vi"/>
		</Item>
		<Item Name="Build Specifications" Type="Build"/>
	</Item>
</Project>
