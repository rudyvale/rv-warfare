package com.norwood.mcheli.vm;

import java.awt.*;
import java.awt.event.*;
import java.nio.file.*;
import java.util.*;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import net.java.games.input.Controller;
import net.java.games.input.Component;

public final class VMCalibration {
    public static volatile boolean showing;
    private final VMController input = new VMController();
    private final JFrame frame = new JFrame("RV · Контроллер и полёт");
    private final JComboBox<String> devices = new JComboBox<String>();
    private final JComboBox<String> kind = new JComboBox<String>(new String[]{"Пульт / RadioMaster / OpenTX / EdgeTX", "Геймпад / PlayStation / Xbox"});
    private final JComboBox<String> flight = new JComboBox<String>(new String[]{"Стабилизация — отпускание стика выравнивает FPV", "Acro — свободное вращение FPV"});
    private final JCheckBox enabled = new JCheckBox("Управлять с контроллера");
    private final JComboBox<String>[] axes = new JComboBox[4];
    private final JCheckBox[] inverse = new JCheckBox[4];
    private final JProgressBar[] meters = new JProgressBar[4];
    private final JComboBox<String>[] bindings = new JComboBox[6];
    private final JLabel status = new JLabel("Подключи устройство по USB в режиме Joystick.");
    private final JButton calibrate = new JButton("1. Запомнить центр");
    private final JSlider deadzone = new JSlider(0, 30, 4), expo = new JSlider(0, 80, 35), rate = new JSlider(45, 240, 110);
    private final double[] lows = new double[4], highs = new double[4], centers = new double[4];
    private final ArrayList<String> axisIds = new ArrayList<String>(), buttonIds = new ArrayList<String>();
    private int stage;
    private boolean selecting;

    public static void open() {
        if (showing) return;
        showing = true;
        SwingUtilities.invokeLater(new Runnable() { public void run() {
            try { new VMCalibration(Paths.get(".")).show(); }
            catch (Throwable error) { showing = false; VMReflect.error("calibration", error); }
        }});
    }

    public VMCalibration(Path root) {
        input.setRoot(root);
        frame.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
        frame.setMinimumSize(new Dimension(850, 650));
        JPanel body = new JPanel(new BorderLayout(12, 12)); body.setBorder(new EmptyBorder(16, 18, 16, 18)); frame.setContentPane(body);
        JPanel top = new JPanel(new GridLayout(0, 1, 4, 4));
        JLabel title = new JLabel("Пульт, геймпад и удобство полёта"); title.setFont(title.getFont().deriveFont(Font.BOLD, 22)); top.add(title);
        top.add(new JLabel("RadioMaster, Jumper, FrSky: USB Joystick. DualShock / DualSense: USB или Bluetooth."));
        JPanel deviceRow = new JPanel(new BorderLayout(8, 0)); deviceRow.add(devices); JButton scan = new JButton("Обновить устройства"); deviceRow.add(scan, BorderLayout.EAST); top.add(deviceRow); top.add(kind); top.add(enabled); body.add(top, BorderLayout.NORTH);
        JTabbedPane tabs = new JTabbedPane();
        JPanel axisPanel = new JPanel(new BorderLayout(8, 12));
        JPanel rows = new JPanel(new GridLayout(5, 4, 8, 10));
        for (String label : new String[]{"Действие", "Ось устройства", "Направление", "Живой сигнал"}) rows.add(new JLabel(label));
        String[] names = {"Крен / танк: прицел X", "Тангаж / танк: прицел Y", "Рыскание / танк: руль", "Газ / танк: вперёд-назад"};
        for (int i = 0; i < 4; i++) {
            rows.add(new JLabel(names[i])); axes[i] = new JComboBox<String>(); rows.add(axes[i]); inverse[i] = new JCheckBox("Инверсия"); rows.add(inverse[i]); meters[i] = new JProgressBar(0, 1000); meters[i].setStringPainted(true); rows.add(meters[i]);
            axes[i].addActionListener(e -> { if (!selecting) { stage = 0; calibrate.setText("1. Запомнить центр"); } });
        }
        axisPanel.add(rows, BorderLayout.NORTH);
        JPanel steps = new JPanel(new GridLayout(0, 1, 5, 5));
        steps.add(new JLabel("1. Выбери оси. Двигай по одному стику и смотри на индикатор."));
        steps.add(new JLabel("2. Все стики, включая газ пульта, в середину → «Запомнить центр»."));
        steps.add(new JLabel("3. Проведи каждым стиком по полному диапазону → «Завершить диапазоны»."));
        steps.add(new JLabel("4. Проверь инверсию: газ вверх — индикатор растёт. Нажми «Сохранить»."));
        steps.add(calibrate); axisPanel.add(steps, BorderLayout.CENTER); tabs.addTab("Оси и калибровка", axisPanel);
        JPanel buttons = new JPanel(new GridLayout(7, 2, 10, 12));
        String[] actionNames = {"Огонь (удерживать)", "Точный прицел (удерживать)", "Следующее оружие", "Тормоз", "Выйти из техники", "Стабилизация / Acro"};
        for (int i = 0; i < 6; i++) { buttons.add(new JLabel(actionNames[i])); bindings[i] = new JComboBox<String>(); buttons.add(bindings[i]); }
        buttons.add(new JLabel("Номер нажатого входа:")); JLabel pressed = new JLabel("—"); buttons.add(pressed); tabs.addTab("Кнопки и переключатели", buttons);
        JPanel tuning = new JPanel(new GridLayout(0, 1, 4, 4)); tuning.add(flight);
        tuning.add(new JLabel("Мёртвая зона (%) — убирает дрожание в центре")); tune(deadzone, 5); tuning.add(deadzone);
        tuning.add(new JLabel("Экспонента (%) — мягче около центра, полный ход сохраняется")); tune(expo, 20); tuning.add(expo);
        tuning.add(new JLabel("Максимальная скорость поворота (градусов/с)")); tune(rate, 45); tuning.add(rate);
        tuning.add(new JLabel("Газ пульта абсолютный. На геймпаде центр удерживает газ, вверх/вниз меняют его."));
        tuning.add(new JLabel("F8 — это окно в игре. При потере фокуса/USB газ сбрасывается."));
        tabs.addTab("Плавность", tuning); body.add(tabs, BorderLayout.CENTER);
        JPanel bottom = new JPanel(new BorderLayout(8, 8)); status.setBorder(new EmptyBorder(5, 0, 5, 0)); bottom.add(status, BorderLayout.NORTH);
        JButton save = new JButton("Сохранить и закрыть"); save.setPreferredSize(new Dimension(250, 38)); bottom.add(save, BorderLayout.EAST); body.add(bottom, BorderLayout.SOUTH);
        enabled.setSelected(input.enabled()); kind.setSelectedIndex(input.gamepad() ? 1 : 0); flight.setSelectedIndex(input.acro() ? 1 : 0);
        deadzone.setValue((int)(input.setting("deadzone", .04) * 100)); expo.setValue((int)(input.setting("expo", .35) * 100)); rate.setValue((int)input.setting("rate", 110));
        scan.addActionListener(e -> rescan()); devices.addActionListener(e -> selectDevice());
        calibrate.addActionListener(e -> calibrate()); save.addActionListener(e -> save());
        javax.swing.Timer timer = new javax.swing.Timer(30, e -> {
            if (input.device == null || !input.device.poll()) { status.setText("Нет сигнала. Проверь USB Joystick и нажми «Обновить устройства»."); return; }
            Component[] all = input.device.getComponents();
            StringBuilder down = new StringBuilder();
            for (int j = 0; j < all.length; j++) if (!all[j].isAnalog() && all[j].getPollData() > 0.5) down.append(j).append(" ");
            pressed.setText(down.length() == 0 ? "— (триггеры видны как оси)" : down.toString());
            for (int i = 0; i < 4; i++) {
                double raw = raw(i);
                if (stage == 1) { lows[i] = Math.min(lows[i], raw); highs[i] = Math.max(highs[i], raw); }
                double out = stage == 2 ? VMControlMath.axis(raw, lows[i], centers[i], highs[i], inverse[i].isSelected(), deadzone.getValue()/100.0, 0) : raw;
                meters[i].setValue((int)(VMControlMath.clamp(out, -1, 1)*500+500)); meters[i].setString(String.format(Locale.ROOT, "%+.2f", out));
            }
        }); timer.start();
        frame.addWindowListener(new WindowAdapter(){ public void windowClosed(WindowEvent e) { timer.stop(); showing = false; } });
        rescan(); frame.pack(); frame.setSize(900, 710); frame.setLocationRelativeTo(null);
    }
    private void tune(JSlider slider, int spacing) { slider.setMajorTickSpacing(spacing); slider.setPaintTicks(true); slider.setPaintLabels(true); }
    private double raw(int i) {
        int selection = axes[i].getSelectedIndex();
        if (input.device == null || selection < 0 || selection >= axisIds.size()) return 0;
        return input.device.getComponents()[Integer.parseInt(axisIds.get(selection))].getPollData();
    }
    private void rescan() {
        selecting = true; devices.removeAllItems(); input.scan();
        int chosen = 0;
        for (int i = 0; i < input.devices.length; i++) { devices.addItem(input.devices[i].getName()); if (VMController.identity(input.devices[i]).equals(input.profile.getProperty("device"))) chosen = i; }
        if (devices.getItemCount() > 0) devices.setSelectedIndex(chosen);
        selecting = false; selectDevice();
    }
    private void selectDevice() {
        if (selecting) return;
        selecting = true;
        int index = devices.getSelectedIndex(); input.device = index < 0 ? null : input.devices[index];
        axisIds.clear(); buttonIds.clear(); buttonIds.add("");
        for (JComboBox<String> b : axes) b.removeAllItems();
        for (JComboBox<String> b : bindings) { b.removeAllItems(); b.addItem("Не назначено"); }
        boolean same = input.device != null && VMController.identity(input.device).equals(input.profile.getProperty("device"));
        if (input.device != null) {
            Component[] all = input.device.getComponents();
            for (int i = 0; i < all.length; i++) {
                Component c = all[i];
                if (c.isAnalog() && !c.isRelative()) {
                    axisIds.add(""+i); for (JComboBox<String> b : axes) b.addItem(i + " · " + c.getName());
                    for (String sign : new String[]{"+", "-"}) { buttonIds.add(i+":"+sign); for (JComboBox<String> b : bindings) b.addItem(i + " · " + c.getName() + " " + sign); }
                } else if (!c.isRelative()) { buttonIds.add(i+":+"); for (JComboBox<String> b : bindings) b.addItem(i + " · " + c.getName()); }
            }
        }
        for (int i = 0; i < 4; i++) {
            String a = VMController.ACTIONS[i]; int selected = same ? axisIds.indexOf(input.profile.getProperty(a+".axis")) : Math.min(i, axisIds.size()-1);
            axes[i].setSelectedIndex(selected); inverse[i].setSelected(same && Boolean.parseBoolean(input.profile.getProperty(a+".invert")));
            centers[i] = input.setting(a+".center", 0); lows[i] = input.setting(a+".min", 0); highs[i] = input.setting(a+".max", 0);
        }
        for (int i = 0; i < 6; i++) bindings[i].setSelectedIndex(Math.max(0, same ? buttonIds.indexOf(input.profile.getProperty("button."+VMController.BUTTONS[i], "")) : 0));
        stage = same && input.mappingValid() ? 2 : 0; calibrate.setText(stage == 2 ? "Калибровать заново" : "1. Запомнить центр");
        selecting = false; status.setText(input.device == null ? "Подключённые контроллеры не найдены." : "Выбери оси и откалибруй стики.");
    }
    private void calibrate() {
        if (input.device == null || !input.device.poll()) return;
        if (stage == 2) { stage = 0; calibrate.setText("1. Запомнить центр"); status.setText("Поставь ВСЕ стики, включая газ, в середину."); return; }
        if (stage == 0) {
            Set<Integer> seen = new HashSet<Integer>();
            for (JComboBox<String> box : axes) if (box.getSelectedIndex()<0 || !seen.add(box.getSelectedIndex())) { status.setText("Для четырёх действий выбери четыре разные оси."); return; }
            for (int i=0;i<4;i++) centers[i]=lows[i]=highs[i]=raw(i);
            stage=1; calibrate.setText("2. Завершить диапазоны"); status.setText("Проведи всеми стиками до краёв во всех направлениях.");
        } else {
            for(int i=0;i<4;i++) if(centers[i]-lows[i]<.08 || highs[i]-centers[i]<.08) { status.setText("Не пройден полный диапазон: " + VMController.ACTIONS[i]); return; }
            stage=2; calibrate.setText("Калибровать заново"); status.setText("Калибровка готова. Проверь направления и сохрани.");
        }
    }
    private void save() {
        if (enabled.isSelected() && (input.device == null || stage != 2)) { status.setText("Сначала заверши калибровку четырёх осей."); return; }
        input.profile.setProperty("enabled", ""+enabled.isSelected()); input.profile.setProperty("kind", kind.getSelectedIndex()==0 ? "radio" : "gamepad"); input.profile.setProperty("flight", flight.getSelectedIndex()==0 ? "angle" : "acro");
        input.profile.setProperty("deadzone", ""+(deadzone.getValue()/100.0)); input.profile.setProperty("expo", ""+(expo.getValue()/100.0)); input.profile.setProperty("rate", ""+rate.getValue());
        if (input.device != null && stage==2) {
            input.profile.setProperty("device", VMController.identity(input.device));
            for(int i=0;i<4;i++) { String a=VMController.ACTIONS[i]; input.profile.setProperty(a+".axis",axisIds.get(axes[i].getSelectedIndex())); input.profile.setProperty(a+".min",""+lows[i]); input.profile.setProperty(a+".max",""+highs[i]); input.profile.setProperty(a+".center",""+centers[i]); input.profile.setProperty(a+".invert",""+inverse[i].isSelected()); }
            for(int i=0;i<6;i++) input.profile.setProperty("button."+VMController.BUTTONS[i], buttonIds.get(bindings[i].getSelectedIndex()));
        }
        try { input.save(); frame.dispose(); } catch(Exception error) { status.setText("Не удалось сохранить: "+error.getMessage()); }
    }
    public void show() { frame.setVisible(true); }
    public void preview(Path path) throws Exception {
        frame.validate();
        java.awt.image.BufferedImage image=new java.awt.image.BufferedImage(frame.getWidth(),frame.getHeight(),java.awt.image.BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics=image.createGraphics(); frame.getRootPane().printAll(graphics); graphics.dispose();
        javax.imageio.ImageIO.write(image,"png",path.toFile());frame.dispose();
    }
    public static void main(String[] args) {
        final Path root = args.length>0 ? Paths.get(args[0]) : Paths.get(".");
        SwingUtilities.invokeLater(() -> { try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); VMCalibration ui=new VMCalibration(root); if(args.length>1)ui.preview(Paths.get(args[1]));else ui.show(); } catch(Exception error){VMReflect.error("controller window",error);} });
    }
}
