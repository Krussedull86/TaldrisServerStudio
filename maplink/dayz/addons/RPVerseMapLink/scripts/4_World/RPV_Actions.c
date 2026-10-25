// Experimental in-game terminal action. Full travel RPC / snapshots still TODO.
class ActionRPVTravel: ActionInteractBase
{
    void ActionRPVTravel()
    {
        m_Text = "Open RPVerse travel";
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!target) return false;
        Object obj = target.GetObject();
        if (!obj) return false;
        return obj.IsKindOf("RPV_TravelTerminal");
    }

    override void OnExecuteClient(ActionData action_data)
    {
        super.OnExecuteClient(action_data);
        PlayerBase player = action_data.m_Player;
        if (player)
            player.MessageStatus("RPVerse terminal detected. Travel menu integration pending.");
    }
};
class RPV_TravelTerminal: ItemBase
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(ActionRPVTravel);
    }
};
