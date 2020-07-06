/* global Vue, window, WebSocket, $ */

window.contentLockingVueInstance = new Vue({
  el: '#presence_alert',
  data: {
    /**
     * The following STATE map shows all the various states of the content
     * locking UI. "Owner" describes the first user into an article; in other
     * words, the article is unlocked and there is no conflict when the Owner
     * begins editing.
     *
     * "Intruder" describes the second user to enter a page, when the Owner
     * already has it opened. There can be multiple intruders.
     *
     * The STATE value is determined either programatically (through the
     * `currentState` computed value) or overridden manually via the
     * `manualState` prop.
     */
    STATE: {
      // Owner's state when an intruder enters the page they are editing
      OWNER_CONFLICT: 'OWNER_CONFLICT',

      // Intruder's state when entering a page that an owner is already editing
      INTRUDER_CONFLICT: 'INTRUDER_CONFLICT',

      // Intruder's state after indicating they want to unlock the page
      INTRUDER_CONFLICT_CONFIRM: 'INTRUDER_CONFLICT_CONFIRM',

      // Intruder's state indicating they want to unlock the page AND the owner
      // has unsaved changes in their version
      INTRUDER_CONFLICT_CONFIRM_DIRTY: 'INTRUDER_CONFLICT_CONFIRM_DIRTY',

      // Owner's state when the intrudcer has forced them out of their article
      OWNER_CONFLICT_FORCED_EXIT: 'OWNER_CONFLICT_FORCED_EXIT',

      // Owner has article opened in multiple tabs/windows
      OWNER_MULTIPLE_TABS: 'OWNER_MULTIPLE_TABS',

      // Owner has been ejected/usurped from the article
      OWNER_USURPED: 'OWNER_USURPED',
    },
    currentUser: null,

    // Serialized page form data; used for checking clean vs. dirty
    initialFormData: null,
    isFormDirty: false,
    isRemoteFormDirty: false,
    manualState: null,
    owner: null,
    socket: null,
    usersPresent: [],
  },

  methods: {
    unlock: function() {
      if (this.isRemoteFormDirty) {
        this.manualState = this.STATE.INTRUDER_CONFLICT_CONFIRM_DIRTY;
        return;
      }
      this.manualState = this.STATE.INTRUDER_CONFLICT_CONFIRM;
    },
    forceUnlock: function() {
      this.socket.send(JSON.stringify({event: 'force_unlock'}));
      this.manualState = null;
    },
    cancelUnlock: function() {
      this.manualState = null;
    },
  },

  mounted: function() {
    var path = window.location.pathname;
    var protocol = window.location.protocol == 'http:' ? 'ws://' : 'wss://';
    this.socket = new WebSocket(
      protocol + window.location.host + '/admin/ws/content_editing' + path,
    );

    this.socket.onmessage = e => {
      var data = JSON.parse(e.data);
      this.usersPresent = [...data.people_here.users_list];
      this.owner = data.people_here.owner;
      this.currentUser = data.current_user;
      this.isRemoteFormDirty = data.people_here.is_dirty;
    };

    // Setup listener to detect if form values have changed & set isFormDirty
    var _this = this;
    _this.initialFormData = $('#page-edit-form').serialize();
    $('#page-edit-form').on('change keyup paste', ':input', function() {
      _this.isFormDirty =
        _this.initialFormData !== $('#page-edit-form').serialize();
    });
  },

  computed: {
    conflicts: function() {
      var _this = this;
      return this.usersPresent.filter(function(item, pos, self) {
        // Removes current user & dedupes usersPresent array
        return item != _this.currentUser && self.indexOf(item) == pos;
      });
    },
    currentState: function() {
      if (this.manualState) {
        return this.manualState;
      }
      if (this.hasConflicts && this.isOwner) {
        return this.STATE.OWNER_CONFLICT;
      }
      if (this.isOpenedInMultipleTabs) {
        return this.STATE.OWNER_MULTIPLE_TABS;
      }
      if (this.hasConflicts && !this.isOwner) {
        return this.STATE.INTRUDER_CONFLICT;
      }
      return null;
    },
    hasConflicts: function() {
      return this.conflicts.length > 0;
    },
    isOpenedInMultipleTabs: function() {
      var _this = this;
      var currentUsers = this.usersPresent.filter(function(x) {
        return x == _this.currentUser;
      });
      return currentUsers.length > 1;
    },
    isOwner: function() {
      return this.owner === this.currentUser;
    },
    locked: function() {
      return this.currentUser !== this.owner;
    },
  },

  watch: {
    /**
     * Based on who the owner of the article is, and that value's changes, set
     * both the conflict state and whether the article form should be locked.
     */
    owner: function(owner, oldOwner) {
      this.manualState = null;

      // Kick out old owner
      if (this.currentUser === oldOwner && this.currentUser !== owner) {
        this.manualState = this.STATE.OWNER_USURPED;
      }
    },

    /** Identifies if the edit body is grey/inaccessible */
    locked: function(locked) {
      $('#page-edit-form :input').prop('disabled', locked);
    },

    /**
     * If the form becomes dirty (or clean), send a websocket message to all
     * users on that page to alter their local isDirty value (used for warning
     * conflicting users before they overwrite changes).
     *
     * This code is here, and not in mounted(), to avoid sending the websocket on
     * every change; it will only be sent when the form goes from clean to
     * dirty, or vice versa.
     */
    isFormDirty: function(dirty) {
      this.socket.send(JSON.stringify({event: 'form_dirty_' + dirty}));
    },
  },
});
