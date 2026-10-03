package rv.experience.protocol;

public final class ExperienceProtocol {
    public static final int MAGIC = 0x52563230;
    public static final int VERSION = 1;
    public static final int REQUEST_BYTES = 22;
    public static final int MAX_SNAPSHOT_BYTES = 32768;
    public static final String CHANNEL = "rvexperience";
    public static final String MOD_ID = "rvexperience";
    public static final String MOD_VERSION = "2.0.0";
    public static final int REQUEST_DISCRIMINATOR = 0;
    public static final int SNAPSHOT_DISCRIMINATOR = 1;

    public enum Action {
        SNAPSHOT, CHOOSE_TEAM, CHOOSE_MODE, CHOOSE_GEAR, SET_READY,
        VOTE_START, CANCEL_VOTE, CONFIRM_GEAR, KEEP_GEAR, OPEN_GUIDE,
        GO_LOBBY, GO_TRAINING, SELECT_PRESET, CHOOSE_LANGUAGE
    }

    public enum Mode { FREEPLAY, TRAINING, TEAM_ROUND }
    public enum Phase { LOBBY, COUNTDOWN, ACTIVE, RESULTS }
    public enum Team { NONE, BLUE, RED, AUTO }
    public enum GearSlot { PRIMARY, SIDEARM, ARMOR, DRONE, MEDICAL, FOOD, AMMO }

    private ExperienceProtocol() { }
}
